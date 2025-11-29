"""
Trip Detection Service - Database operations and orchestration for trip detection
"""
import threading
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.config import SessionLocal

from backend.lib.config_manager import config_manager
from backend.database.models import (
    Email, EmailContent, EmailTransportSegment, EmailAccommodation,
    EmailTourActivity, EmailCruise
)
from backend.lib.ai.ai_provider_with_fallback import AIProviderWithFallback
from backend.lib.trip_detector import TripDetector
from backend.models.trip import Trip
from backend.models.booking import BookingInfo
from backend.constants import TRAVEL_CATEGORIES
from backend.models.repositories.trip_repository import TripRepository

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Temporarily enable debug logging


class TripDetectionService:
    """Service for detecting and organizing trips from travel emails - handles database operations and orchestration"""
    
    def __init__(self):
        self.ai_provider: Optional[AIProviderWithFallback] = None
        self.trip_detector: Optional[TripDetector] = None
        
        # Define fallback order for trip detection
        self.provider_fallback_order = [
            ('gemini', 'powerful'),
            ('gemini', 'fast')
        ]
        
        try:
            # Create AI provider with fallback support
            self.ai_provider = AIProviderWithFallback(self.provider_fallback_order)
            self.trip_detector = TripDetector(self.ai_provider)
            
            model_info = self.ai_provider.get_model_info()
            logger.info(f"Trip detection AI provider initialized with fallback support. Primary model: {model_info['model_name']}")
        except Exception as e:
            logger.error(f"Failed to initialize AI provider with fallback: {e}")
            self.ai_provider = None
            self.trip_detector = None
        
        # Progress tracking with thread safety
        self.detection_progress = {
            'is_running': False,
            'total_emails': 0,
            'processed_emails': 0,
            'trips_found': 0,
            'current_batch': 0,
            'total_batches': 0,
            'finished': False,
            'error': None,
            'message': ''
        }
        self._stop_flag = threading.Event()
        self._detection_thread = None
        self._lock = threading.Lock()
    
    def start_detection(self, date_range: Optional[Dict] = None) -> Dict:
        """Start trip detection process"""
        with self._lock:
            if self.detection_progress.get('is_running', False):
                return {"started": False, "message": "Trip detection already in progress"}
            
            if self._detection_thread and self._detection_thread.is_alive():
                return {"started": False, "message": "Detection thread already running"}
            
            if not self.ai_provider or not self.trip_detector:
                return {"started": False, "message": "AI provider service not available"}
            
            # Reset progress
            self._stop_flag.clear()
            self.detection_progress = {
                'is_running': True,
                'total_emails': 0,
                'processed_emails': 0,
                'trips_found': 0,
                'current_batch': 0,
                'total_batches': 0,
                'finished': False,
                'error': None,
                'message': 'Starting trip detection...',
                'start_time': datetime.now()
            }
            
            # Start background thread
            self._detection_thread = threading.Thread(
                target=self._background_detection,
                args=(date_range,),
                daemon=True
            )
            self._detection_thread.start()
            
            return {"started": True, "message": "Trip detection started"}
    
    def stop_detection(self) -> str:
        """Stop ongoing detection process"""
        with self._lock:
            self._stop_flag.set()
            if self.detection_progress.get('is_running', False):
                self.detection_progress['is_running'] = False
                self.detection_progress['finished'] = True
                self.detection_progress['message'] = 'Detection stopped by user'
        return "Stop signal sent"
    
    def get_detection_progress(self) -> Dict:
        """Get current detection progress"""
        progress = self.detection_progress.copy()
        
        # Calculate progress percentage
        if progress['total_emails'] > 0:
            progress['progress'] = int((progress['processed_emails'] / progress['total_emails']) * 100)
        else:
            progress['progress'] = 0
            
        return progress
    
    
    def _load_existing_trips_from_database(self, db: Session) -> List[Dict]:
        """Load all existing trips from database and convert to dictionary format for AI"""
        try:
            # Use repository to get all trips
            trip_repository = TripRepository(db)
            trips = trip_repository.find_all()
            
            # Convert Trip domain objects to dictionaries
            existing_trips = [trip.to_dict() for trip in trips]
            
            logger.info(f"Loaded {len(existing_trips)} existing trips from database")
            return existing_trips
            
        except Exception as e:
            logger.error(f"Error loading existing trips from database: {e}")
            raise Exception(f"Failed to load existing trips: {e}")
    
    def _background_detection(self, date_range: Optional[Dict] = None):
        """Background process for trip detection"""
        db = SessionLocal()
        try:
            # Clear existing trips only at the start of the entire detection process
            # This prevents data loss if individual batches fail
            should_clear_trips = date_range and date_range.get('reset_trips', False)
            if should_clear_trips:
                logger.info("Resetting all trips as requested")
                trip_repository = TripRepository(db)
                trip_repository.delete_all()
                existing_trips = []
            else:
                # Load existing trips from database first
                try:
                    existing_trips = self._load_existing_trips_from_database(db)
                    logger.info(f"Starting with {len(existing_trips)} existing trips from database")
                except Exception as e:
                    logger.error(f"CRITICAL: Failed to load existing trips from database: {e}")
                    with self._lock:
                        self.detection_progress.update({
                            'finished': True,
                            'is_running': False,
                            'error': f'Failed to load existing trips: {str(e)}',
                            'message': f'Detection failed: Unable to load existing trips from database'
                        })
                    return  # Exit early to prevent data loss
            
            # Fetch all travel-related emails with extracted content
            # Check for stuck emails in processing status
            stuck_count = db.query(Email).join(EmailContent).filter(
                Email.classification.in_(TRAVEL_CATEGORIES),
                EmailContent.extraction_status == 'completed',
                EmailContent.booking_extraction_status == 'completed',
                EmailContent.trip_detection_status == 'processing'
            ).count()
            
            if stuck_count > 0:
                logger.warning(f"Found {stuck_count} emails stuck in 'processing' status - resetting them to 'pending'")
                # Reset stuck emails to pending
                db.query(EmailContent).filter(
                    EmailContent.email_id.in_(
                        db.query(Email.email_id).join(EmailContent).filter(
                            Email.classification.in_(TRAVEL_CATEGORIES),
                            EmailContent.extraction_status == 'completed',
                            EmailContent.booking_extraction_status == 'completed',
                            EmailContent.trip_detection_status == 'processing'
                        )
                    )
                ).update({
                    'trip_detection_status': 'pending',
                    'trip_detection_error': 'Reset from stuck processing status'
                }, synchronize_session=False)
                db.commit()
                logger.info(f"Reset {stuck_count} stuck emails to 'pending' status")
            
            # Only get emails that have actual booking information
            # Filter out non-booking emails directly in the database
            query = db.query(Email).join(EmailContent).filter(
                Email.classification.in_(TRAVEL_CATEGORIES),
                EmailContent.extraction_status == 'completed',
                EmailContent.booking_extraction_status == 'completed',  # This excludes 'no_booking' status
                EmailContent.trip_detection_status.in_(['pending', 'failed']),  # Only pending and failed, since we reset stuck ones
                # Filter for emails with actual bookings by checking the extracted_booking_info
                EmailContent.extracted_booking_info.isnot(None),
                # Ensure the booking info contains a booking_type (not null)
                func.json_extract(EmailContent.extracted_booking_info, '$.booking_type').isnot(None)
            )
            
            if date_range:
                if 'start_date' in date_range:
                    query = query.filter(Email.timestamp >= date_range['start_date'])
                if 'end_date' in date_range:
                    query = query.filter(Email.timestamp <= date_range['end_date'])
            
            # Order by timestamp for chronological processing
            emails = query.order_by(Email.timestamp.asc()).all()
            
            if not emails:
                with self._lock:
                    self.detection_progress.update({
                        'finished': True,
                        'is_running': False,
                        'message': 'No travel emails found for detection'
                    })
                return
            
            # Update progress
            self.detection_progress['total_emails'] = len(emails)
            
            # Log initial email count
            logger.info(f"Total booking emails found (excluding non-booking emails): {len(emails)}")
            
            self.detection_progress['message'] = f'Found {len(emails)} travel emails to analyze'
            
            # Fixed batch size for provider fallback strategy
            batch_size = config_manager.get_trip_detection_batch_size()  # Process in moderate batches
            total_batches = (len(emails) + batch_size - 1) // batch_size  # Calculate total number of batches
            self.detection_progress['total_batches'] = total_batches
            
            # Reset provider index for new detection run
            self._current_provider_index = 0
            
            # Start with existing trips from database
            all_trips = existing_trips.copy()
            
            # Process emails with adaptive batch sizing
            processed_emails = 0
            batch_num = 0
            
            while processed_emails < len(emails) and not self._stop_flag.is_set():
                batch_num += 1
                remaining_emails = len(emails) - processed_emails
                current_batch_size = min(batch_size, remaining_emails)
                
                batch_emails = emails[processed_emails:processed_emails + current_batch_size]
                
                self.detection_progress['current_batch'] = batch_num
                self.detection_progress['message'] = f'Processing batch {batch_num} (size: {current_batch_size}, with {len(all_trips)} existing trips)'
                
                # Always pass ALL current trips (existing from database + newly detected)
                # IMPORTANT: Pass empty list [] instead of None when there are no trips
                previous_trips = all_trips.copy() if all_trips else []
                
                logger.info(f"Batch {batch_num}: Processing {len(batch_emails)} emails (batch size: {current_batch_size})")
                
                # Mark emails as processing
                self._mark_emails_processing(batch_emails, db)
                
                # Convert emails to format expected by TripDetector
                logger.debug(f"Batch {batch_num}: About to prepare email data for {len(batch_emails)} emails")
                email_data, invalid_emails = BookingInfo.prepare_emails_for_trip_detection(batch_emails)
                logger.debug(f"Batch {batch_num}: Prepared {len(email_data)} email data entries")
                
                # Mark invalid emails as failed
                if invalid_emails:
                    # Group emails by reason
                    emails_by_reason = {}
                    for email, reason in invalid_emails:
                        if reason not in emails_by_reason:
                            emails_by_reason[reason] = []
                        emails_by_reason[reason].append(email)
                    
                    # Mark each group with its specific reason
                    for reason, email_list in emails_by_reason.items():
                        self._mark_emails_failed(email_list, db, reason)
                
                # Skip this batch if all emails were incomplete
                if not email_data:
                    logger.warning(f"Batch {batch_num}: All emails had incomplete booking information, skipping batch")
                    processed_emails += current_batch_size
                    self.detection_progress['processed_emails'] = processed_emails
                    continue
                
                # Try to process this batch
                batch_success = False
                
                while not batch_success and not self._stop_flag.is_set():
                    try:
                        logger.info(f"Batch {batch_num}: Processing {len(email_data)} booking emails (batch size: {current_batch_size})")
                        
                        # Debug logging for previous_trips
                        logger.debug(f"Batch {batch_num}: previous_trips type: {type(previous_trips)}")
                        if previous_trips:
                            logger.debug(f"Batch {batch_num}: previous_trips length: {len(previous_trips)}")
                            logger.debug(f"Batch {batch_num}: previous_trips[0] type: {type(previous_trips[0]) if previous_trips else 'N/A'}")
                        
                        batch_trips = self.trip_detector.detect_trips(email_data, previous_trips)

                        # Check if detection actually succeeded
                        if batch_trips is None:
                            raise Exception("Trip detection returned None - likely an AI API error")

                        # Success! Validate and update trips
                        if batch_trips:
                            # Debug logging for batch_trips
                            logger.debug(f"Batch {batch_num}: batch_trips type: {type(batch_trips)}")
                            logger.debug(f"Batch {batch_num}: batch_trips length: {len(batch_trips)}")
                            if batch_trips:
                                logger.debug(f"Batch {batch_num}: batch_trips[0] type: {type(batch_trips[0])}")
                                
                            # Validate that AI provider returned at least the existing trips
                            if previous_trips and len(batch_trips) < len(previous_trips):
                                logger.error(f"Batch {batch_num}: CRITICAL - AI provider returned {len(batch_trips)} trips but we sent {len(previous_trips)} existing trips. This indicates the AI dropped existing trips!")
                                
                                # Debug before accessing .get()
                                logger.debug(f"About to access .get() on previous_trips items. Type check: {[type(trip) for trip in previous_trips[:3]]}")
                                logger.error(f"Sent existing trips: {[trip.get('name', 'Unknown') for trip in previous_trips]}")
                                logger.error(f"Received trips: {[trip.get('name', 'Unknown') for trip in batch_trips]}")
                                
                                # Safety fallback: merge the trips ourselves to prevent data loss
                                logger.warning("Performing safety merge to prevent trip data loss")
                                all_trips = TripRepository.merge_trip_data(previous_trips, batch_trips)
                                logger.info(f"Safety merge resulted in {len(all_trips)} trips")
                            else:
                                all_trips = batch_trips
                                logger.info(f"Batch {batch_num}: Successfully updated to {len(all_trips)} total trips (expected at least {len(previous_trips) if previous_trips else 0})")
                        else:
                            logger.warning(f"Batch {batch_num}: No trips returned from AI provider")
                            # Don't clear existing trips or mark emails as completed if we got no results
                            # This might be a temporary failure - keep all_trips unchanged

                        # Only proceed with saving if we actually got trips back
                        if batch_trips is not None:
                            # Save trips after each successful batch to prevent data loss
                            if all_trips:
                                # Replace all trips with the current state
                                self._replace_all_trips_in_database(all_trips, db)
                                logger.info(f"Batch {batch_num}: Saved {len(all_trips)} trips to database")
                            else:
                                logger.info(f"Batch {batch_num}: No trips to save")
                            
                            # Only mark emails as completed AFTER successfully saving trips
                            self._mark_emails_completed(batch_emails, db)
                            
                            batch_success = True
                        else:
                            # AI call failed - don't mark as success
                            logger.error(f"Batch {batch_num}: AI call failed, not marking emails as completed")
                            batch_success = False
                        
                        # Reset to first provider for next batch (start with most stable)
                        if self._current_provider_index > 0 and batch_success:
                            provider_name, model_tier = self.provider_fallback_order[0]
                            logger.info(f"Resetting to primary provider ({provider_name}-{model_tier}) for next batch")
                            self._current_provider_index = 0
                            provider_name, model_tier = self.provider_fallback_order[0]
                            try:
                                self.ai_provider = AIProviderFactory.create_provider(
                                    model_tier=model_tier,
                                    provider_name=provider_name
                                )
                                self.trip_detector = TripDetector(self.ai_provider)
                            except Exception as e:
                                logger.warning(f"Failed to reset to primary provider: {e}")
                        
                    except Exception as e:
                        error_msg = str(e)
                        # Log full stack trace for debugging
                        import traceback
                        logger.error(f"Batch {batch_num} failed: {error_msg}")
                        logger.error(f"Full stack trace:\n{traceback.format_exc()}")
                        
                        # The AIProviderWithFallback already handles retries internally
                        # If we get here, all providers have been exhausted
                        logger.error("All providers failed for this batch. Marking emails as failed.")
                        self._mark_emails_failed(batch_emails, db, f"Trip detection failed: {error_msg}")
                        
                        # Continue with next batch instead of stopping entirely
                        processed_emails += current_batch_size
                        self.detection_progress['processed_emails'] = processed_emails
                        break  # Exit retry loop for this batch
                
                # Only advance if batch was successful
                if batch_success:
                    processed_emails += current_batch_size
                    self.detection_progress['processed_emails'] = processed_emails
                    self.detection_progress['trips_found'] = len(all_trips)
            
            # No need for final save since we save after each batch
            # Trips are already saved incrementally
            
            # Mark as finished
            with self._lock:
                self.detection_progress.update({
                    'finished': True,
                    'is_running': False,
                    'message': f'Detection completed. Found {len(all_trips)} trips.'
                })
            
        except Exception as e:
            logger.error(f"Trip detection failed: {e}")
            with self._lock:
                self.detection_progress.update({
                    'finished': True,
                    'is_running': False,
                    'error': str(e),
                    'message': f'Detection failed: {str(e)}'
                })
        finally:
            db.close()
    
    
    
    def _mark_emails_processing(self, emails: List[Email], db: Session):
        """Mark emails as being processed for trip detection"""
        try:
            for email in emails:
                if email.email_content:
                    email.email_content.trip_detection_status = 'processing'
            db.commit()
            logger.info(f"Marked {len(emails)} emails as processing")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark emails as processing: {e}")
    
    def _mark_emails_completed(self, emails: List[Email], db: Session):
        """Mark emails as successfully processed for trip detection"""
        try:
            for email in emails:
                if email.email_content:
                    email.email_content.trip_detection_status = 'completed'
                    email.email_content.trip_detection_processed_at = datetime.now()
                    email.email_content.trip_detection_error = None
            db.commit()
            logger.info(f"Marked {len(emails)} emails as completed")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark emails as completed: {e}")
    
    def _mark_emails_failed(self, emails: List[Email], db: Session, error_message: str):
        """Mark emails as failed during trip detection"""
        try:
            for email in emails:
                if email.email_content:
                    email.email_content.trip_detection_status = 'failed'
                    email.email_content.trip_detection_error = error_message
            db.commit()
            logger.info(f"Marked {len(emails)} emails as failed")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark emails as failed: {e}")
    
    def _mark_emails_pending(self, emails: List[Email], db: Session):
        """Reset emails back to pending status for retry"""
        try:
            for email in emails:
                if email.email_content:
                    email.email_content.trip_detection_status = 'pending'
                    email.email_content.trip_detection_error = None
            db.commit()
            logger.info(f"Reset {len(emails)} emails to pending status")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to reset emails to pending: {e}")
    
    

    def _replace_all_trips_in_database(self, trips: List[Dict], db: Session):
        """Replace all trips in database with new set of trips"""
        try:
            # Create repository instance
            trip_repository = TripRepository(db)

            # Convert all trip dictionaries to Trip domain objects
            trip_objects = []
            for trip_data in trips:
                try:
                    trip = Trip.from_json(trip_data)
                    trip_objects.append(trip)
                except Exception as e:
                    logger.error(f"Failed to create trip object for '{trip_data.get('name', 'Unknown')}': {e}")
                    # Log the trip data to understand what's missing
                    logger.debug(f"Failed trip data: {json.dumps(trip_data, indent=2, default=str)[:500]}...")
                    # Continue with other trips
                    continue

            # SAFETY CHECK: Only replace if we have valid trips to save
            # This prevents data loss when a batch fails to generate trips
            if not trip_objects:
                logger.warning("No valid trip objects to save - skipping database replacement to prevent data loss")
                return

            # Use repository to replace all trips
            saved_count = trip_repository.replace_all_trips(trip_objects)
            logger.info(f"Successfully replaced all trips. Saved {saved_count} trips to database")

        except Exception as e:
            logger.error(f"Failed to replace trips in database: {e}")
            raise
    
    
    def reset_trip_detection_status(self) -> Dict:
        """Reset trip detection status for all emails and clear all trips"""
        db = SessionLocal()
        try:
            # Clear all trips and related data
            trip_repository = TripRepository(db)
            trip_repository.delete_all()
            
            # Reset all email trip detection status
            # Reset all travel emails with completed booking extraction
            # First get the email IDs that need to be reset
            email_ids_to_reset = db.query(Email.email_id).join(EmailContent).filter(
                Email.classification.in_(TRAVEL_CATEGORIES),
                EmailContent.extraction_status == 'completed',
                EmailContent.booking_extraction_status.in_(['completed', 'no_booking'])
            ).all()
            
            email_ids = [e[0] for e in email_ids_to_reset]
            
            # Then update the EmailContent records
            if email_ids:
                reset_count = db.query(EmailContent).filter(
                    EmailContent.email_id.in_(email_ids)
                ).update({
                    EmailContent.trip_detection_status: 'pending',
                    EmailContent.trip_detection_error: None
                }, synchronize_session=False)
            else:
                reset_count = 0
            
            db.commit()
            
            logger.info(f"Reset trip detection status for {reset_count} emails and cleared all trips")
            return {
                "success": True,
                "message": f"Reset {reset_count} emails and cleared all trips",
                "emails_reset": reset_count
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to reset trip detection status: {e}")
            return {
                "success": False,
                "message": f"Failed to reset: {str(e)}"
            }
        finally:
            db.close()
