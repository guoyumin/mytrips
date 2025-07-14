"""
Email Processing Orchestrator - Coordinates email processing pipeline
"""
import json
import logging
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta

from backend.database.config import SessionLocal
from backend.database.models import Email, EmailContent
from backend.lib.gmail_client import GmailClient
from backend.lib.email_classifier import EmailClassifier
from backend.lib.ai.ai_provider_with_fallback import AIProviderWithFallback
from backend.lib.config_manager import config_manager
from backend.constants import TRAVEL_CATEGORIES

from ..micro.import_micro_service import ImportMicroService
from ..micro.classification_micro_service import ClassificationMicroService
from ..micro.content_extraction_micro_service import ContentExtractionMicroService
from ..micro.booking_extraction_micro_service import BookingExtractionMicroService

logger = logging.getLogger(__name__)


class EmailProcessingOrchestrator:
    """
    Orchestrates the entire email processing pipeline
    
    Responsibilities:
    - Coordinate microservices
    - Handle database writes
    - Manage processing flow
    - Track overall progress
    """
    
    def __init__(self):
        """Initialize orchestrator with microservices"""
        # Initialize Gmail client
        credentials_path = config_manager.get_gmail_credentials_path()
        token_path = config_manager.get_gmail_token_path()
        self.gmail_client = GmailClient(credentials_path, token_path)
        
        # Initialize AI providers
        classification_providers = [
            ('deepseek', 'powerful'),
            ('gemma3', 'powerful')
        ]
        booking_providers = [
            ('gemini', 'fast'),
            ('openai', 'fast')
        ]
        
        classification_ai = AIProviderWithFallback(classification_providers)
        booking_ai = AIProviderWithFallback(booking_providers)
        
        # Initialize microservices
        self.import_micro = ImportMicroService(self.gmail_client)
        self.classification_micro = ClassificationMicroService(
            EmailClassifier(classification_ai)
        )
        self.content_micro = ContentExtractionMicroService(self.gmail_client)
        self.booking_micro = BookingExtractionMicroService(booking_ai)
        
        logger.info("EmailProcessingOrchestrator initialized")
    
    def import_and_process_date_range(self,
                                     start_date: datetime,
                                     end_date: datetime,
                                     process_immediately: bool = True,
                                     batch_callback: Optional[Callable] = None) -> Dict:
        """
        Import emails for date range and optionally start processing
        
        Args:
            start_date: Start date for import
            end_date: End date for import
            process_immediately: Whether to start classification immediately
            batch_callback: Optional callback for each batch imported
            
        Returns:
            Import results with processing status
        """
        logger.info(f"Starting import for date range: {start_date} to {end_date}")
        
        # 1. Import emails using microservice
        import_result = self.import_micro.import_emails_by_date_range(
            start_date, end_date
        )
        
        if not import_result['emails']:
            logger.info("No new emails to import")
            return import_result
        
        # 2. Save imported emails to database in batches
        batch_size = 50
        emails = import_result['emails']
        saved_count = 0
        
        db = SessionLocal()
        try:
            for i in range(0, len(emails), batch_size):
                batch = emails[i:i + batch_size]
                email_ids = []
                
                # Save batch to database
                for email_data in batch:
                    # Check if email already exists (defensive)
                    existing = db.query(Email).filter_by(
                        email_id=email_data['email_id']
                    ).first()
                    
                    if not existing:
                        email = Email(**email_data)
                        db.add(email)
                        email_ids.append(email_data['email_id'])
                        saved_count += 1
                
                db.commit()
                logger.info(f"Saved batch {i//batch_size + 1}: {len(email_ids)} emails")
                
                # Optional callback for parallel processing
                if batch_callback and email_ids:
                    batch_callback(email_ids)
                
                # Start classification if requested
                if process_immediately and email_ids:
                    self.process_classification(email_ids)
            
            import_result['saved_count'] = saved_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save emails: {e}")
            raise
        finally:
            db.close()
        
        return import_result
    
    def import_and_process_days(self, 
                               days: int,
                               process_immediately: bool = True,
                               batch_callback: Optional[Callable] = None) -> Dict:
        """
        Import emails from last N days (backward compatibility)
        
        Args:
            days: Number of days to import
            process_immediately: Whether to start classification
            batch_callback: Optional callback for each batch
            
        Returns:
            Import results
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.import_and_process_date_range(
            start_date, end_date, process_immediately, batch_callback
        )
    
    def process_classification(self, 
                             email_ids: Optional[List[str]] = None,
                             limit: Optional[int] = None,
                             auto_continue: bool = True) -> Dict:
        """
        Process email classification
        
        Args:
            email_ids: Specific emails to classify (if None, find unclassified)
            limit: Max emails to process
            auto_continue: Whether to continue with content extraction
            
        Returns:
            Classification results
        """
        db = SessionLocal()
        try:
            # 1. Determine which emails to classify
            if not email_ids:
                # Find unclassified emails
                query = db.query(Email.email_id).filter(
                    Email.classification == 'unclassified'
                )
                if limit:
                    query = query.limit(limit)
                email_ids = [row[0] for row in query.all()]
            
            if not email_ids:
                logger.info("No emails to classify")
                return {'classified_count': 0}
            
            logger.info(f"Classifying {len(email_ids)} emails")
            
            # 2. Call classification microservice
            result = self.classification_micro.classify_emails(email_ids)
            
            # 3. Save classification results
            travel_email_ids = []
            for classification in result['classifications']:
                email = db.query(Email).filter_by(
                    email_id=classification['email_id']
                ).first()
                
                if email:
                    email.classification = classification['classification']
                    # Collect travel emails for next stage
                    if classification['classification'] in TRAVEL_CATEGORIES:
                        travel_email_ids.append(classification['email_id'])
            
            db.commit()
            logger.info(f"Saved {len(result['classifications'])} classifications, {len(travel_email_ids)} travel emails")
            
            # 4. Auto-continue with content extraction
            if auto_continue and travel_email_ids:
                self.process_content_extraction(travel_email_ids)
            
            result['travel_email_ids'] = travel_email_ids
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"Classification failed: {e}")
            raise
        finally:
            db.close()
    
    def process_content_extraction(self,
                                  email_ids: Optional[List[str]] = None,
                                  limit: Optional[int] = None,
                                  auto_continue: bool = True) -> Dict:
        """
        Process content extraction for travel emails
        
        Args:
            email_ids: Specific emails to extract (if None, find travel emails)
            limit: Max emails to process
            auto_continue: Whether to continue with booking extraction
            
        Returns:
            Extraction results
        """
        db = SessionLocal()
        try:
            # 1. Determine which emails need content extraction
            if not email_ids:
                email_ids = self.content_micro.get_emails_needing_content(limit=limit)
            
            if not email_ids:
                logger.info("No emails need content extraction")
                return {'extracted_count': 0}
            
            logger.info(f"Extracting content for {len(email_ids)} emails")
            
            # 2. Call content extraction microservice
            result = self.content_micro.extract_content(email_ids)
            
            # 3. Save extraction results
            emails_for_booking = []
            
            for extraction in result['results']:
                if extraction['status'] != 'success':
                    continue
                
                # Create or update EmailContent record
                content = db.query(EmailContent).filter_by(
                    email_id=extraction['email_id']
                ).first()
                
                if not content:
                    content = EmailContent(email_id=extraction['email_id'])
                    db.add(content)
                
                # Update content
                content.content_text = extraction.get('content_text', '')
                content.content_html = extraction.get('content_html', '')
                content.has_attachments = extraction.get('has_attachments', False)
                content.attachments_info = json.dumps(extraction.get('attachments', []))
                content.attachments_count = extraction.get('attachments_count', 0)
                content.extraction_status = 'completed'
                content.extracted_at = datetime.now()
                
                emails_for_booking.append(extraction['email_id'])
            
            db.commit()
            logger.info(f"Saved {len(emails_for_booking)} content extractions")
            
            # 4. Auto-continue with booking extraction
            if auto_continue and emails_for_booking:
                self.process_booking_extraction(emails_for_booking)
            
            result['emails_for_booking'] = emails_for_booking
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"Content extraction failed: {e}")
            raise
        finally:
            db.close()
    
    def process_booking_extraction(self,
                                  email_ids: Optional[List[str]] = None,
                                  limit: Optional[int] = None) -> Dict:
        """
        Process booking extraction
        
        Args:
            email_ids: Specific emails to process (if None, find emails needing extraction)
            limit: Max emails to process
            
        Returns:
            Booking extraction results
        """
        db = SessionLocal()
        try:
            # 1. Determine which emails need booking extraction
            if not email_ids:
                email_ids = self.booking_micro.get_emails_needing_booking_extraction(limit=limit)
            
            if not email_ids:
                logger.info("No emails need booking extraction")
                return {'extracted_count': 0}
            
            logger.info(f"Extracting bookings from {len(email_ids)} emails")
            
            # 2. Call booking extraction microservice
            result = self.booking_micro.extract_bookings(email_ids)
            
            # 3. Save booking results
            for booking in result['bookings']:
                if booking['status'] != 'success':
                    continue
                
                content = db.query(EmailContent).filter_by(
                    email_id=booking['email_id']
                ).first()
                
                if not content:
                    logger.warning(f"No content record for email {booking['email_id']}")
                    continue
                
                # Check if email was reclassified
                if not booking.get('is_travel', True):
                    # Update email classification
                    email = db.query(Email).filter_by(
                        email_id=booking['email_id']
                    ).first()
                    if email:
                        email.classification = booking.get('actual_category', 'not_travel')
                    
                    content.booking_extraction_status = 'not_travel'
                    content.booking_extraction_error = booking.get('reason', 'Not a travel email')
                    content.extraction_status = 'not_required'
                    
                elif booking.get('booking_info', {}).get('booking_type') is None:
                    # Non-booking travel email
                    content.booking_extraction_status = 'no_booking'
                    content.booking_extraction_error = booking.get('reason', 'Non-booking email')
                    
                else:
                    # Successful booking extraction
                    content.extracted_booking_info = json.dumps(
                        booking.get('booking_info', {}), 
                        ensure_ascii=False
                    )
                    content.booking_extraction_status = 'completed'
                    content.booking_extraction_error = None
            
            db.commit()
            logger.info(f"Saved {result['success_count']} booking extractions")
            
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"Booking extraction failed: {e}")
            raise
        finally:
            db.close()
    
    def process_full_pipeline(self,
                             start_date: datetime,
                             end_date: datetime) -> Dict:
        """
        Run the full pipeline: import -> classify -> extract content -> extract bookings
        
        Args:
            start_date: Start date for import
            end_date: End date for import
            
        Returns:
            Complete pipeline results
        """
        logger.info("Starting full email processing pipeline")
        
        results = {
            'import': {},
            'classification': {},
            'content_extraction': {},
            'booking_extraction': {}
        }
        
        try:
            # 1. Import emails
            results['import'] = self.import_and_process_date_range(
                start_date, end_date, 
                process_immediately=False  # We'll handle it manually
            )
            
            # 2. Classify all imported emails
            if results['import'].get('saved_count', 0) > 0:
                email_ids = [e['email_id'] for e in results['import']['emails']]
                results['classification'] = self.process_classification(
                    email_ids, auto_continue=False
                )
                
                # 3. Extract content for travel emails
                travel_ids = results['classification'].get('travel_email_ids', [])
                if travel_ids:
                    results['content_extraction'] = self.process_content_extraction(
                        travel_ids, auto_continue=False
                    )
                    
                    # 4. Extract bookings
                    content_ids = results['content_extraction'].get('emails_for_booking', [])
                    if content_ids:
                        results['booking_extraction'] = self.process_booking_extraction(
                            content_ids
                        )
            
            logger.info("Full pipeline completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            results['error'] = str(e)
            raise