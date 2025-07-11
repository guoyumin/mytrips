"""
Trip Detection Service - Database operations and orchestration for trip detection
"""
import threading
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.config import SessionLocal
from database.models import (
    Email, EmailContent, Trip, TransportSegment, Accommodation, 
    TourActivity, Cruise, EmailTransportSegment, EmailAccommodation,
    EmailTourActivity, EmailCruise
)
from lib.ai.ai_provider_factory import AIProviderFactory
from lib.ai.ai_provider_interface import AIProviderInterface
from lib.trip_detector import TripDetector

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Temporarily enable debug logging


class TripDetectionService:
    """Service for detecting and organizing trips from travel emails - handles database operations and orchestration"""
    
    def __init__(self):
        self.ai_provider: Optional[AIProviderInterface] = None
        self.trip_detector: Optional[TripDetector] = None
        
        # Provider fallback order: openai-fast -> gemini-fast -> claude-fast
        self.provider_fallback_order = [
            ('deepseek', 'powerful'),
            ('gemini', 'fast'),
            ('openai', 'fast')
        ]
        
        try:
            # Create AI provider using factory - start with openai-fast (more stable)
            self.ai_provider = AIProviderFactory.create_provider(
                model_tier='fast', 
                provider_name='openai'
            )
            self.trip_detector = TripDetector(self.ai_provider)
            
            model_info = self.ai_provider.get_model_info()
            logger.info(f"AI provider initialized: {model_info['model_name']}")
        except Exception as e:
            logger.error(f"Failed to initialize AI provider: {e}")
        
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
        self._current_provider_index = 0  # Track current provider in fallback order
    
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
    
    def _switch_to_next_provider(self) -> bool:
        """Switch to the next provider in the fallback order. Returns True if successful."""
        self._current_provider_index += 1
        
        if self._current_provider_index >= len(self.provider_fallback_order):
            logger.error("All providers exhausted in fallback order")
            return False
        
        provider_name, model_tier = self.provider_fallback_order[self._current_provider_index]
        
        try:
            logger.info(f"Switching to fallback provider: {provider_name}-{model_tier}")
            self.ai_provider = AIProviderFactory.create_provider(
                model_tier=model_tier,
                provider_name=provider_name
            )
            self.trip_detector = TripDetector(self.ai_provider)
            
            model_info = self.ai_provider.get_model_info()
            logger.info(f"Successfully switched to: {model_info['model_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch to {provider_name}-{model_tier}: {e}")
            # Try next provider recursively
            return self._switch_to_next_provider()
    
    def _load_existing_trips_from_database(self, db: Session) -> List[Dict]:
        """Load all existing trips from database and convert to AI provider format"""
        try:
            trips = db.query(Trip).all()
            existing_trips = []
            
            for trip in trips:
                # Convert database trip to AI provider format
                trip_dict = {
                    'name': trip.name,
                    'destination': trip.destination,
                    'start_date': trip.start_date.strftime('%Y-%m-%d') if trip.start_date else None,
                    'end_date': trip.end_date.strftime('%Y-%m-%d') if trip.end_date else None,
                    'cities_visited': json.loads(trip.cities_visited) if trip.cities_visited else [],
                    'total_cost': float(trip.total_cost) if trip.total_cost else 0.0,
                    'transport_segments': [],
                    'accommodations': [],
                    'tour_activities': [],
                    'cruises': []
                }
                
                # Load transport segments
                for segment in trip.transport_segments:
                    segment_dict = {
                        'segment_type': segment.segment_type,
                        'departure_location': segment.departure_location,
                        'arrival_location': segment.arrival_location,
                        'departure_datetime': segment.departure_datetime.isoformat() if segment.departure_datetime else None,
                        'arrival_datetime': segment.arrival_datetime.isoformat() if segment.arrival_datetime else None,
                        'carrier_name': segment.carrier_name,
                        'segment_number': segment.segment_number,
                        'distance_km': float(segment.distance_km) if segment.distance_km else None,
                        'distance_type': segment.distance_type,
                        'cost': float(segment.cost) if segment.cost else 0.0,
                        'booking_platform': segment.booking_platform,
                        'confirmation_number': segment.confirmation_number,
                        'status': segment.status,
                        'is_latest_version': segment.is_latest_version,
                        'related_email_ids': [email.email_id for email in segment.emails]
                    }
                    trip_dict['transport_segments'].append(segment_dict)
                
                # Load accommodations
                for accommodation in trip.accommodations:
                    accommodation_dict = {
                        'property_name': accommodation.property_name,
                        'check_in_date': accommodation.check_in_date.strftime('%Y-%m-%d') if accommodation.check_in_date else None,
                        'check_out_date': accommodation.check_out_date.strftime('%Y-%m-%d') if accommodation.check_out_date else None,
                        'address': accommodation.address,
                        'city': accommodation.city,
                        'country': accommodation.country,
                        'cost': float(accommodation.cost) if accommodation.cost else 0.0,
                        'booking_platform': accommodation.booking_platform,
                        'confirmation_number': accommodation.confirmation_number,
                        'status': accommodation.status,
                        'is_latest_version': accommodation.is_latest_version,
                        'related_email_ids': [email.email_id for email in accommodation.emails]
                    }
                    trip_dict['accommodations'].append(accommodation_dict)
                
                # Load tour activities
                for activity in trip.tour_activities:
                    activity_dict = {
                        'activity_name': activity.activity_name,
                        'description': activity.description,
                        'start_datetime': activity.start_datetime.isoformat() if activity.start_datetime else None,
                        'end_datetime': activity.end_datetime.isoformat() if activity.end_datetime else None,
                        'location': activity.location,
                        'city': activity.city,
                        'cost': float(activity.cost) if activity.cost else 0.0,
                        'booking_platform': activity.booking_platform,
                        'confirmation_number': activity.confirmation_number,
                        'status': activity.status,
                        'is_latest_version': activity.is_latest_version,
                        'related_email_ids': [email.email_id for email in activity.emails]
                    }
                    trip_dict['tour_activities'].append(activity_dict)
                
                # Load cruises
                for cruise in trip.cruises:
                    cruise_dict = {
                        'cruise_line': cruise.cruise_line,
                        'ship_name': cruise.ship_name,
                        'departure_datetime': cruise.departure_datetime.isoformat() if cruise.departure_datetime else None,
                        'arrival_datetime': cruise.arrival_datetime.isoformat() if cruise.arrival_datetime else None,
                        'itinerary': json.loads(cruise.itinerary) if cruise.itinerary else [],
                        'cost': float(cruise.cost) if cruise.cost else 0.0,
                        'booking_platform': cruise.booking_platform,
                        'confirmation_number': cruise.confirmation_number,
                        'status': cruise.status,
                        'is_latest_version': cruise.is_latest_version,
                        'related_email_ids': [email.email_id for email in cruise.emails]
                    }
                    trip_dict['cruises'].append(cruise_dict)
                
                existing_trips.append(trip_dict)
            
            logger.info(f"Loaded {len(existing_trips)} existing trips from database")
            return existing_trips
            
        except Exception as e:
            logger.error(f"Error loading existing trips from database: {e}")
            raise Exception(f"Failed to load existing trips: {e}")
    
    def _background_detection(self, date_range: Optional[Dict] = None):
        """Background process for trip detection"""
        db = SessionLocal()
        try:
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
            travel_categories = [
                'flight', 'hotel', 'car_rental', 'train', 'cruise', 
                'tour', 'travel_insurance', 'flight_change', 
                'hotel_change', 'other_travel'
            ]
            
            # Check for stuck emails in processing status
            stuck_count = db.query(Email).join(EmailContent).filter(
                Email.classification.in_(travel_categories),
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
                            Email.classification.in_(travel_categories),
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
                Email.classification.in_(travel_categories),
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
            
            # Calculate cost estimation
            # Rough estimate: 1000 input tokens and 500 output tokens per email
            estimated_input_tokens = len(emails) * 1000
            estimated_output_tokens = len(emails) * 500
            cost_estimate = self.ai_provider.estimate_cost(estimated_input_tokens, estimated_output_tokens)
            self.detection_progress['cost_estimate'] = cost_estimate
            
            self.detection_progress['message'] = f'Found {len(emails)} travel emails to analyze (Est. cost: ${cost_estimate["estimated_cost_usd"]:.4f})'
            
            # Fixed batch size for provider fallback strategy
            batch_size = 10  # Process in moderate batches
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
                previous_trips = all_trips.copy() if all_trips else None
                
                logger.info(f"Batch {batch_num}: Processing {len(batch_emails)} emails (batch size: {current_batch_size})")
                
                # Mark emails as processing
                self._mark_emails_processing(batch_emails, db)
                
                # Convert emails to format expected by TripDetector
                logger.debug(f"Batch {batch_num}: About to prepare email data for {len(batch_emails)} emails")
                email_data = self._prepare_email_data(batch_emails, db)
                logger.debug(f"Batch {batch_num}: Prepared {len(email_data)} email data entries")
                
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
                                all_trips = self._safe_merge_trips(previous_trips, batch_trips)
                                logger.info(f"Safety merge resulted in {len(all_trips)} trips")
                            else:
                                all_trips = batch_trips
                                logger.info(f"Batch {batch_num}: Successfully updated to {len(all_trips)} total trips (expected at least {len(previous_trips) if previous_trips else 0})")
                        else:
                            logger.warning(f"Batch {batch_num}: No trips returned from AI provider")
                        
                        # Save current trip state to database immediately after successful detection
                        self._clear_existing_trips(db)
                        if all_trips:
                            self._save_trips_to_database(all_trips, db)
                            logger.info(f"Batch {batch_num}: Saved {len(all_trips)} trips to database")
                        else:
                            logger.info(f"Batch {batch_num}: No trips to save")
                        
                        # Only mark emails as completed AFTER successfully saving trips
                        self._mark_emails_completed(batch_emails, db)
                        
                        batch_success = True
                        
                        # Reset to first provider for next batch (start with most stable)
                        if self._current_provider_index > 0:
                            logger.info("Resetting to primary provider (openai-fast) for next batch")
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
                        logger.error(f"Batch {batch_num} failed with {self.ai_provider.get_model_info()['model_name']}: {error_msg}")
                        logger.error(f"Full stack trace:\n{traceback.format_exc()}")
                        
                        # Try switching to next provider in fallback order
                        if self._switch_to_next_provider():
                            # Get current provider info for logging
                            model_info = self.ai_provider.get_model_info()
                            self.detection_progress['message'] = f'Retrying batch {batch_num} with {model_info["model_name"]}'
                            logger.info(f"Retrying batch {batch_num} with fallback provider: {model_info['model_name']}")
                            # Continue retry loop with new provider
                            continue
                        else:
                            # All providers exhausted
                            logger.error("All providers failed. Stopping detection.")
                            self._mark_emails_failed(batch_emails, db, "All AI providers failed")
                            
                            with self._lock:
                                self.detection_progress.update({
                                    'finished': True,
                                    'is_running': False,
                                    'error': 'Detection stopped: all AI providers failed'
                                })
                            return
                
                # Only advance if batch was successful
                if batch_success:
                    processed_emails += current_batch_size
                    self.detection_progress['processed_emails'] = processed_emails
                    self.detection_progress['trips_found'] = len(all_trips)
            
            # Trips are already saved after each successful batch
            
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
    
    def _clear_existing_trips(self, db: Session):
        """Clear all existing trips and related data from database"""
        try:
            # Delete in proper order to respect foreign key constraints
            db.query(EmailTransportSegment).delete()
            db.query(EmailAccommodation).delete()
            db.query(EmailTourActivity).delete()
            db.query(EmailCruise).delete()
            
            db.query(TransportSegment).delete()
            db.query(Accommodation).delete()
            db.query(TourActivity).delete()
            db.query(Cruise).delete()
            
            db.query(Trip).delete()
            
            db.commit()
            logger.info("Cleared all existing trips from database")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error clearing existing trips: {e}")
            raise
    
    def _is_zurich_local_trip(self, extracted_booking: Dict) -> bool:
        """Check if this is a Zurich local trip (zone tickets, local transport)"""
        booking_type = extracted_booking.get('booking_type')
        
        # Check for zone tickets or local transport indicators
        if booking_type == 'train':
            additional_info = extracted_booking.get('additional_info', {})
            # Handle case where additional_info might be None
            if additional_info is None:
                additional_info = {}
            notes = additional_info.get('notes', '')
            # Check for ZVV zone tickets or extensions
            if any(indicator in notes.lower() for indicator in ['zvv extension', 'zone ticket', 'zones', 'tageskarte']):
                return True
                
            # Check if both departure and arrival are in Zurich area
            # Use new field name and expect array format
            transport_segments = extracted_booking.get('transport_segments', [])
            
            # Check if any segment is a Zurich local trip
            for segment in transport_segments:
                departure = (segment.get('departure_location') or '').lower()
                arrival = (segment.get('arrival_location') or '').lower()
                zurich_areas = ['zurich', 'zürich', 'winterthur', 'oerlikon', 'altstetten', 'stadelhofen']
                if any(area in departure for area in zurich_areas) and any(area in arrival for area in zurich_areas):
                    return True
                    
        return False
    
    def _is_email_complete(self, extracted_booking: Dict) -> bool:
        """Check if email has minimum required booking information for trip detection"""
        booking_type = extracted_booking.get('booking_type')
        
        if not booking_type:
            logger.debug("Email incomplete: missing booking_type")
            return False
            
        # Be more lenient - only require minimal information
        if booking_type == 'flight':
            # For flights, we at least need departure datetime
            transport_segments = extracted_booking.get('transport_segments', [])
            
            if not transport_segments:
                logger.debug(f"Flight booking incomplete: no transport_segments found")
                return False
                
            # Only require departure datetime, be lenient with other fields
            for segment in transport_segments:
                if not (segment.get('departure_datetime') or segment.get('departure_date')):
                    logger.debug(f"Flight booking incomplete: missing departure datetime")
                    return False
                    
        elif booking_type == 'hotel':
            # Check for accommodations array
            accommodations = extracted_booking.get('accommodations', [])
            
            if not accommodations:
                logger.debug("Hotel booking incomplete: no accommodations found")
                return False
            
            # For hotels, be lenient - only require property name OR check-in date
            for accommodation in accommodations:
                if not accommodation.get('property_name') and not accommodation.get('check_in_date'):
                    logger.debug("Hotel booking incomplete: missing both property name and check-in date")
                    return False
                
        elif booking_type == 'tour':
            # Check for activities array
            activities = extracted_booking.get('activities', [])
            
            if not activities:
                logger.debug("Tour booking incomplete: no activities found")
                return False
            
            # For tours, be lenient - only require activity name OR date
            for activity in activities:
                has_name = activity.get('activity_name') or activity.get('tour_name')
                has_date = (activity.get('start_datetime') or activity.get('start_date') or 
                           activity.get('activity_date'))
                
                if not has_name and not has_date:
                    logger.debug("Tour booking incomplete: missing both name and date")
                    return False
                
        elif booking_type == 'train':
            # Similar to flights, check for departure information
            transport_segments = extracted_booking.get('transport_segments', [])
            
            if not transport_segments:
                logger.debug("Train booking incomplete: no transport_segments found")
                return False
                
            # Check if any segment has departure time
            has_departure_time = any(
                segment.get('departure_datetime') or segment.get('departure_date')
                for segment in transport_segments
            )
            
            if not has_departure_time:
                logger.debug(f"Train booking incomplete: missing departure datetime")
                return False
                
        # For other types, just check if there's basic info
        return True
    
    def _prepare_email_data(self, emails: List[Email], db: Session) -> List[Dict]:
        """Convert Email objects to format expected by TripDetector"""
        email_data = []
        incomplete_emails = []
        
        for i, email in enumerate(emails):
            try:
                logger.debug(f"Processing email {i+1}/{len(emails)}: {email.email_id}")
                content = email.email_content
                
                # Use extracted booking information instead of raw content
                extracted_booking = {}
                if content and content.extracted_booking_info:
                    try:
                        extracted_booking = json.loads(content.extracted_booking_info)
                    except Exception as e:
                        logger.warning(f"Failed to parse extracted booking info for {email.email_id}: {e}")
                        extracted_booking = {}
                
                # Check if this is a Zurich local trip
                if self._is_zurich_local_trip(extracted_booking):
                    booking_type = extracted_booking.get('booking_type', 'unknown')
                    logger.info(f"Skipping Zurich local trip email {email.email_id} (type: {booking_type}, subject: {email.subject[:50]}...)")
                    incomplete_emails.append((email, "Zurich local trip - zone ticket or local transport"))
                    continue
                
                # Check if email has complete information
                if not self._is_email_complete(extracted_booking):
                    booking_type = extracted_booking.get('booking_type', 'unknown')
                    logger.warning(f"Skipping email {email.email_id} (type: {booking_type}, subject: {email.subject[:50]}...) due to incomplete booking information")
                    logger.debug(f"Email {email.email_id} booking data: {json.dumps(extracted_booking, indent=2)}")
                    incomplete_emails.append((email, "Incomplete booking information"))
                    continue
                    
                email_info = {
                    'email_id': email.email_id,
                    'subject': email.subject,
                    'sender': email.sender,
                    'date': email.timestamp.isoformat() if email.timestamp else email.date,
                    'classification': email.classification,
                    'extracted_booking_info': extracted_booking
                }
                email_data.append(email_info)
                
            except Exception as e:
                logger.error(f"Error processing email {email.email_id}: {e}")
                import traceback
                logger.error(f"Stack trace: {traceback.format_exc()}")
                incomplete_emails.append((email, f"Processing error: {str(e)}"))
        
        # Mark incomplete emails as failed with specific reasons
        if incomplete_emails:
            # Group emails by reason
            emails_by_reason = {}
            for email, reason in incomplete_emails:
                if reason not in emails_by_reason:
                    emails_by_reason[reason] = []
                emails_by_reason[reason].append(email)
            
            # Mark each group with its specific reason
            for reason, email_list in emails_by_reason.items():
                self._mark_emails_failed(email_list, db, reason)
            
        return email_data
    
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
    
    def _safe_parse_datetime(self, date_str):
        """Safely parse datetime string"""
        if not date_str:
            return None
        if isinstance(date_str, str):
            try:
                return datetime.fromisoformat(date_str)
            except ValueError:
                # Try parsing other common formats
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Could not parse date: {date_str}")
                    return None
        return None
    
    def _safe_parse_date(self, date_str):
        """Safely parse date string"""
        if not date_str:
            return None
        if isinstance(date_str, str):
            try:
                return datetime.fromisoformat(date_str).date()
            except ValueError:
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    logger.warning(f"Could not parse date: {date_str}")
                    return None
        return None
    
    def _safe_merge_trips(self, previous_trips: List[Dict], new_trips: List[Dict]) -> List[Dict]:
        """Safely merge previous and new trips to prevent data loss"""
        try:
            # Create a map of existing trips by name for easy lookup
            existing_trip_map = {}
            for trip in previous_trips:
                trip_name = trip.get('name', 'Unknown')
                existing_trip_map[trip_name] = trip
            
            # Start with all previous trips
            merged_trips = previous_trips.copy()
            
            # Add or update with new trips
            for new_trip in new_trips:
                new_trip_name = new_trip.get('name', 'Unknown')
                
                if new_trip_name in existing_trip_map:
                    # This trip exists, replace it with the updated version
                    for i, trip in enumerate(merged_trips):
                        if trip.get('name') == new_trip_name:
                            merged_trips[i] = new_trip
                            logger.info(f"Updated existing trip: {new_trip_name}")
                            break
                else:
                    # This is a new trip, add it
                    merged_trips.append(new_trip)
                    logger.info(f"Added new trip: {new_trip_name}")
            
            logger.info(f"Safe merge completed: {len(previous_trips)} previous + {len(new_trips)} new → {len(merged_trips)} total")
            return merged_trips
            
        except Exception as e:
            logger.error(f"Error in safe merge, falling back to previous trips: {e}")
            return previous_trips

    def _save_trips_to_database(self, trips: List[Dict], db: Session):
        """Save detected trips and their components to database"""
        data_quality_issues = []  # Track any data quality issues
        try:
            for trip_data in trips:
                # Validate and provide defaults for required fields
                trip_name = trip_data.get('name')
                if not trip_name:
                    trip_name = f"Trip to {trip_data.get('destination', 'Unknown')}"
                    logger.warning(f"Missing trip name, using default: {trip_name}")
                
                # Create Trip record
                trip = Trip(
                    name=trip_name,
                    destination=trip_data.get('destination'),
                    start_date=self._safe_parse_date(trip_data.get('start_date')),
                    end_date=self._safe_parse_date(trip_data.get('end_date')),
                    origin_city='Zurich',
                    cities_visited=json.dumps(trip_data.get('cities_visited', [])),
                    ai_analysis=json.dumps(trip_data.get('ai_analysis', {}))
                )
                db.add(trip)
                db.flush()  # Get trip ID
                
                # Save transport segments
                for segment_data in trip_data.get('transport_segments', []):
                    # Validate required fields for TransportSegment
                    segment_type = segment_data.get('segment_type')
                    departure_location = segment_data.get('departure_location')
                    arrival_location = segment_data.get('arrival_location')
                    departure_dt = self._safe_parse_datetime(segment_data.get('departure_datetime'))
                    arrival_dt = self._safe_parse_datetime(segment_data.get('arrival_datetime'))
                    
                    # Be more lenient - only skip if we don't have minimal required fields
                    if not (segment_type and departure_dt):
                        error_msg = f"Missing critical fields for transport segment: type={segment_type}, dep_dt={departure_dt}"
                        logger.error(error_msg)
                        
                        # Track data quality issue
                        related_emails = segment_data.get('related_email_ids', [])
                        data_quality_issues.append({
                            'type': 'transport_segment',
                            'error': error_msg,
                            'email_ids': related_emails
                        })
                        continue
                    
                    # Use defaults for missing non-critical fields
                    if not departure_location:
                        departure_location = "Unknown departure"
                        logger.warning(f"Missing departure location for {segment_type}, using default")
                    
                    if not arrival_location:
                        arrival_location = "Unknown arrival"
                        logger.warning(f"Missing arrival location for {segment_type}, using default")
                    
                    if not arrival_dt:
                        # Estimate arrival time based on segment type
                        if segment_type == 'flight':
                            arrival_dt = departure_dt + timedelta(hours=2)  # Default 2 hour flight
                        elif segment_type == 'train':
                            arrival_dt = departure_dt + timedelta(hours=3)  # Default 3 hour train
                        else:
                            arrival_dt = departure_dt + timedelta(hours=4)  # Default 4 hours
                        logger.warning(f"Missing arrival datetime for {segment_type}, estimated as {arrival_dt}")
                    
                    segment = TransportSegment(
                        trip_id=trip.id,
                        segment_type=segment_type,
                        departure_location=departure_location,
                        arrival_location=arrival_location,
                        departure_datetime=departure_dt,
                        arrival_datetime=arrival_dt,
                        distance_km=segment_data.get('distance_km'),
                        distance_type=segment_data.get('distance_type'),
                        cost=segment_data.get('cost', 0.0),
                        booking_platform=segment_data.get('booking_platform'),
                        carrier_name=segment_data.get('carrier_name'),
                        segment_number=segment_data.get('segment_number'),
                        confirmation_number=segment_data.get('confirmation_number'),
                        status=segment_data.get('status', 'confirmed'),
                        is_latest_version=segment_data.get('is_latest_version', True)
                    )
                    db.add(segment)
                    db.flush()
                    
                    # Link emails
                    for email_id in segment_data.get('related_email_ids', []):
                        link = EmailTransportSegment(
                            email_id=email_id,
                            transport_segment_id=segment.id
                        )
                        db.add(link)
                
                # Save accommodations
                for accommodation_data in trip_data.get('accommodations', []):
                    # Validate required fields for Accommodation
                    property_name = accommodation_data.get('property_name')
                    check_in_date = self._safe_parse_date(accommodation_data.get('check_in_date'))
                    check_out_date = self._safe_parse_date(accommodation_data.get('check_out_date'))
                    
                    # Be more lenient - only skip if we have neither property name nor check-in date
                    if not (property_name or check_in_date):
                        error_msg = "Missing both property name and check-in date for accommodation"
                        logger.error(error_msg)
                        
                        # Track data quality issue
                        related_emails = accommodation_data.get('related_email_ids', [])
                        data_quality_issues.append({
                            'type': 'accommodation',
                            'error': error_msg,
                            'email_ids': related_emails
                        })
                        continue
                    
                    # Use defaults for missing fields
                    if not property_name:
                        property_name = "Unknown accommodation"
                        logger.warning("Missing property name, using default")
                    
                    if not check_in_date:
                        # Try to infer from trip dates
                        if trip.start_date:
                            check_in_date = trip.start_date.date() if hasattr(trip.start_date, 'date') else trip.start_date
                        logger.warning(f"Missing check-in date, using trip start date: {check_in_date}")
                    
                    if not check_out_date:
                        # Default to 1 night stay or trip end date
                        if check_in_date:
                            check_out_date = check_in_date + timedelta(days=1)
                        elif trip.end_date:
                            check_out_date = trip.end_date.date() if hasattr(trip.end_date, 'date') else trip.end_date
                        logger.warning(f"Missing check-out date, estimated as {check_out_date}")
                    
                    accommodation = Accommodation(
                        trip_id=trip.id,
                        property_name=property_name,
                        check_in_date=check_in_date,
                        check_out_date=check_out_date,
                        address=accommodation_data.get('address'),
                        city=accommodation_data.get('city'),
                        country=accommodation_data.get('country'),
                        cost=accommodation_data.get('cost', 0.0),
                        booking_platform=accommodation_data.get('booking_platform'),
                        confirmation_number=accommodation_data.get('confirmation_number'),
                        status=accommodation_data.get('status', 'confirmed'),
                        is_latest_version=accommodation_data.get('is_latest_version', True)
                    )
                    db.add(accommodation)
                    db.flush()
                    
                    # Link emails
                    for email_id in accommodation_data.get('related_email_ids', []):
                        link = EmailAccommodation(
                            email_id=email_id,
                            accommodation_id=accommodation.id
                        )
                        db.add(link)
                
                # Save tour activities
                for tour_data in trip_data.get('tour_activities', []):
                    # Validate required fields for TourActivity
                    activity_name = tour_data.get('activity_name')
                    start_dt = self._safe_parse_datetime(tour_data.get('start_datetime'))
                    end_dt = self._safe_parse_datetime(tour_data.get('end_datetime'))
                    
                    # Skip if activity_name is missing
                    if not activity_name:
                        error_msg = f"Missing activity_name for tour activity in email: {email_id}"
                        logger.error(error_msg)
                        
                        # Track data quality issue
                        related_emails = tour_data.get('related_email_ids', [])
                        data_quality_issues.append({
                            'type': 'tour_activity',
                            'error': error_msg,
                            'email_ids': related_emails
                        })
                        continue
                    
                    # Skip if start_datetime is missing
                    if not start_dt:
                        error_msg = f"Missing start_datetime for activity '{activity_name}'"
                        logger.error(error_msg)
                        
                        # Track data quality issue
                        related_emails = tour_data.get('related_email_ids', [])
                        data_quality_issues.append({
                            'type': 'tour_activity',
                            'error': error_msg,
                            'email_ids': related_emails
                        })
                        continue
                    
                    # If end_datetime is missing, estimate it based on start_datetime
                    if not end_dt:
                        # Default to 4 hours after start time for tours/activities
                        end_dt = start_dt + timedelta(hours=4)
                        logger.warning(f"Missing end_datetime for activity '{activity_name}', estimated as {end_dt}")
                    
                    tour = TourActivity(
                        trip_id=trip.id,
                        activity_name=activity_name,
                        description=tour_data.get('description'),
                        start_datetime=start_dt,
                        end_datetime=end_dt,
                        location=tour_data.get('location'),
                        city=tour_data.get('city'),
                        cost=tour_data.get('cost', 0.0),
                        booking_platform=tour_data.get('booking_platform'),
                        confirmation_number=tour_data.get('confirmation_number'),
                        status=tour_data.get('status', 'confirmed'),
                        is_latest_version=tour_data.get('is_latest_version', True)
                    )
                    db.add(tour)
                    db.flush()
                    
                    # Link emails
                    for email_id in tour_data.get('related_email_ids', []):
                        link = EmailTourActivity(
                            email_id=email_id,
                            tour_activity_id=tour.id
                        )
                        db.add(link)
                
                # Save cruises
                for cruise_data in trip_data.get('cruises', []):
                    # Validate required fields for Cruise
                    cruise_line = cruise_data.get('cruise_line')
                    departure_dt = self._safe_parse_datetime(cruise_data.get('departure_datetime'))
                    arrival_dt = self._safe_parse_datetime(cruise_data.get('arrival_datetime'))
                    
                    # Skip cruise if any required field is missing
                    if not all([cruise_line, departure_dt, arrival_dt]):
                        error_msg = (f"Missing required fields for cruise: "
                                   f"line={cruise_line}, dep_dt={departure_dt}, arr_dt={arrival_dt}")
                        logger.error(error_msg)
                        
                        # Track data quality issue
                        related_emails = cruise_data.get('related_email_ids', [])
                        data_quality_issues.append({
                            'type': 'cruise',
                            'error': error_msg,
                            'email_ids': related_emails
                        })
                        continue
                    
                    cruise = Cruise(
                        trip_id=trip.id,
                        cruise_line=cruise_line,
                        ship_name=cruise_data.get('ship_name'),
                        departure_datetime=departure_dt,
                        arrival_datetime=arrival_dt,
                        itinerary=json.dumps(cruise_data.get('itinerary', [])),
                        cost=cruise_data.get('cost', 0.0),
                        booking_platform=cruise_data.get('booking_platform'),
                        confirmation_number=cruise_data.get('confirmation_number'),
                        status=cruise_data.get('status', 'confirmed'),
                        is_latest_version=cruise_data.get('is_latest_version', True)
                    )
                    db.add(cruise)
                    db.flush()
                    
                    # Link emails
                    for email_id in cruise_data.get('related_email_ids', []):
                        link = EmailCruise(
                            email_id=email_id,
                            cruise_id=cruise.id
                        )
                        db.add(link)
            
            db.commit()
            logger.info(f"Successfully saved {len(trips)} trips to database")
            
            # Update email status for emails with data quality issues
            if data_quality_issues:
                self._update_emails_with_data_quality_issues(data_quality_issues, db)
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save trips to database: {e}")
            raise
    
    def _update_emails_with_data_quality_issues(self, issues: List[Dict], db: Session):
        """Update email status for emails with data quality issues"""
        try:
            # Collect all unique email IDs with issues
            email_ids_with_issues = set()
            issue_summary = {}
            
            for issue in issues:
                for email_id in issue.get('email_ids', []):
                    email_ids_with_issues.add(email_id)
                    if email_id not in issue_summary:
                        issue_summary[email_id] = []
                    issue_summary[email_id].append(f"{issue['type']}: {issue['error']}")
            
            # Update each email with data quality issues
            for email_id in email_ids_with_issues:
                email = db.query(Email).filter_by(email_id=email_id).first()
                if email and email.email_content:
                    # Append data quality issues to existing error or create new one
                    existing_error = email.email_content.trip_detection_error or ""
                    quality_errors = "\n".join(issue_summary[email_id])
                    
                    if existing_error:
                        email.email_content.trip_detection_error = f"{existing_error}\nDATA QUALITY ISSUES:\n{quality_errors}"
                    else:
                        email.email_content.trip_detection_error = f"DATA QUALITY ISSUES:\n{quality_errors}"
                    
                    # Keep status as completed but with errors noted
                    logger.warning(f"Email {email_id} has data quality issues: {quality_errors}")
            
            db.commit()
            logger.info(f"Updated {len(email_ids_with_issues)} emails with data quality issues")
            
        except Exception as e:
            logger.error(f"Failed to update emails with data quality issues: {e}")
            # Don't rollback main transaction, just log the error
