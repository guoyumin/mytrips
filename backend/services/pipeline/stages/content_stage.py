"""
Content Extraction Stage for Email Pipeline
"""
import logging
import threading
from typing import Dict, List, Optional
from sqlalchemy import and_

from backend.services.pipeline.base_stage import BasePipelineStage
from backend.services.email_content_service import EmailContentService
from backend.database.models import Email, EmailContent
from backend.constants import TRAVEL_CATEGORIES

logger = logging.getLogger(__name__)


class ContentExtractionStage(BasePipelineStage):
    """Stage for extracting content from travel emails"""
    
    def __init__(self, batch_size: int = 20):
        super().__init__("Content Extraction", batch_size)
        
        # Initialize content service
        self.content_service = EmailContentService()
        
        # Track extracted emails
        self.content_extracted_emails = set()
        self.extraction_started = False
    
    def check_pending_work(self) -> Optional[List[str]]:
        """Check for travel emails that need content extraction"""
        db = self.get_db_session()
        try:
            pending_emails = db.query(Email.email_id).filter(
                Email.classification.in_(TRAVEL_CATEGORIES)
            ).outerjoin(
                EmailContent, Email.email_id == EmailContent.email_id
            ).filter(
                EmailContent.email_id == None  # No content extracted yet
            ).all()
            
            if pending_emails:
                email_ids = [email[0] for email in pending_emails]
                logger.info(f"Found {len(email_ids)} travel emails pending content extraction")
                return email_ids
            
            return None
        finally:
            db.close()
    
    def process_batch(self, batch_data: Dict) -> Dict:
        """Process a batch of emails for content extraction"""
        email_ids = batch_data.get('email_ids', [])
        
        if not email_ids:
            return {}
        
        logger.info(f"Starting content extraction for {len(email_ids)} emails")
        
        # Start extraction using the service
        extraction_result = self.content_service.start_extraction(email_ids=email_ids)
        
        if not extraction_result.get('started'):
            logger.error(f"Failed to start content extraction: {extraction_result.get('message')}")
            logger.error(f"Current extraction progress: {self.content_service.get_extraction_progress()}")
            return {}
        
        self.extraction_started = True
        
        # Monitor extraction progress
        last_extracted_count = 0
        batch_extracted_email_ids = []  # Only emails extracted in THIS batch
        
        logger.info(f"Content extraction: Monitoring extraction progress for {len(email_ids)} emails")
        check_count = 0
        while not self.is_stopped():
            progress = self.content_service.get_extraction_progress()
            check_count += 1
            
            # Log progress every 5 checks
            if check_count % 5 == 0:
                logger.info(f"Content extraction progress: {progress.get('extracted_count', 0)}/{progress.get('total', 0)} extracted, {progress.get('failed_count', 0)} failed")
            
            # Update our progress
            self.update_progress(
                processed=len(self.content_extracted_emails) + progress.get('extracted_count', 0),
                total=self.progress.get('total', 0) + len(email_ids),
                failed=progress.get('failed_count', 0)
            )
            
            # Check for newly extracted emails
            current_extracted = progress.get('extracted_count', 0)
            if current_extracted > last_extracted_count:
                # Get emails with extracted content
                new_extracted = self._get_newly_extracted_emails(email_ids, current_extracted - last_extracted_count)
                
                if new_extracted:
                    batch_extracted_email_ids.extend(new_extracted)
                    self.content_extracted_emails.update(new_extracted)
                    logger.info(f"Extracted content from {len(new_extracted)} emails")
                
                last_extracted_count = current_extracted
            
            # Check if extraction is finished
            if progress.get('finished', False):
                logger.info("Content extraction batch completed")
                break
            
            # Wait before checking again
            threading.Event().wait(1)
        
        # Return only emails extracted in this batch for booking extraction
        if batch_extracted_email_ids:
            return {
                'email_ids': batch_extracted_email_ids,
                'batch_size': len(batch_extracted_email_ids)
            }
        
        return {}
    
    def run_extraction(self, input_queue, output_queue):
        """
        Run the content extraction process
        
        Args:
            input_queue: Queue receiving travel email IDs from classification
            output_queue: Queue to send extracted emails to booking extraction
        """
        try:
            self.start()
            
            # Check for pending work but don't process it automatically
            # Only process if explicitly requested by pipeline
            pending_work = self.check_pending_work()
            if pending_work:
                logger.info(f"Content extraction: Found {len(pending_work)} pending emails in database")
                # Process pending emails in batches
                for i in range(0, len(pending_work), self.batch_size):
                    if self.is_stopped():
                        break
                    
                    batch_ids = pending_work[i:i+self.batch_size]
                    logger.info(f"Content extraction: Processing pending batch with {len(batch_ids)} emails")
                    result = self.process_batch({'email_ids': batch_ids, 'batch_size': len(batch_ids)})
                    
                    if result and result.get('email_ids'):
                        logger.info(f"Content extraction: Sending {len(result['email_ids'])} extracted emails to booking stage")
                        output_queue.put(result)
            else:
                logger.info("Content extraction stage ready, no pending emails found")
            
            # Process incoming batches
            logger.info("Content extraction stage: Starting to process incoming batches from classification")
            batch_count = 0
            while not self.is_stopped():
                try:
                    # Get batch from classification stage
                    logger.debug("Content extraction: Waiting for batch from classification queue...")
                    batch = input_queue.get(timeout=1.0)
                    
                    # Check for end signal
                    if batch is None:
                        logger.info("Content extraction: Received end signal from classification stage")
                        
                        # Wait for any ongoing extraction to complete
                        if self.extraction_started:
                            logger.info("Content extraction: Waiting for ongoing extraction to complete...")
                            wait_count = 0
                            while not self.is_stopped():
                                progress = self.content_service.get_extraction_progress()
                                wait_count += 1
                                if wait_count % 5 == 0:  # Log every 5 seconds
                                    logger.info(f"Content extraction: Still waiting... Progress: {progress.get('extracted_count', 0)}/{progress.get('total', 0)}")
                                if progress.get('finished', False):
                                    logger.info("Content extraction: Extraction finished")
                                    break
                                threading.Event().wait(1)
                        
                        # Check for any remaining extracted emails
                        self._send_remaining_extracted_emails(output_queue)
                        
                        # Signal end to next stage
                        output_queue.put(None)
                        break
                    
                    batch_count += 1
                    logger.info(f"Content extraction: Received batch #{batch_count} with {batch.get('batch_size', 0)} emails")
                    
                    # Process the batch
                    result = self.process_batch(batch)
                    
                    # Send extracted emails to booking extraction
                    if result and result.get('email_ids'):
                        logger.info(f"Content extraction: Sending {len(result['email_ids'])} extracted emails to booking stage")
                        output_queue.put(result)
                    else:
                        logger.info("Content extraction: No emails extracted from this batch")
                    
                except Exception as e:
                    if e.__class__.__name__ == 'Empty':  # queue.Empty
                        continue
                    else:
                        logger.error(f"Content extraction: Error processing batch - {e}")
                        raise
            
            self.complete()
            
        except Exception as e:
            logger.error(f"Content extraction stage failed: {e}")
            self.fail(str(e))
            raise
    
    def _get_newly_extracted_emails(self, email_ids: List[str], limit: int) -> List[str]:
        """Get emails that were just extracted"""
        db = self.get_db_session()
        try:
            new_extracted = db.query(EmailContent.email_id).filter(
                EmailContent.email_id.in_(email_ids),
                EmailContent.extraction_status == 'completed',
                ~EmailContent.email_id.in_(self.content_extracted_emails)
            ).limit(limit).all()
            
            return [email[0] for email in new_extracted]
        finally:
            db.close()
    
    def _send_remaining_extracted_emails(self, output_queue):
        """Send any remaining extracted emails to booking extraction"""
        db = self.get_db_session()
        try:
            remaining_extracted = db.query(EmailContent.email_id).filter(
                and_(
                    EmailContent.extraction_status == 'completed',
                    EmailContent.booking_extraction_status.in_(['pending', 'failed']),
                    ~EmailContent.email_id.in_(self.content_extracted_emails)
                )
            ).join(
                Email, EmailContent.email_id == Email.email_id
            ).filter(
                Email.classification.in_(TRAVEL_CATEGORIES)
            ).all()
            
            if remaining_extracted:
                remaining_ids = [email[0] for email in remaining_extracted]
                self.content_extracted_emails.update(remaining_ids)
                
                # Send to booking extraction
                output_queue.put({
                    'email_ids': remaining_ids,
                    'batch_size': len(remaining_ids)
                })
                
                logger.info(f"Sent {len(remaining_ids)} remaining emails for booking extraction")
        finally:
            db.close()
    
    def stop(self):
        """Stop content extraction stage"""
        super().stop()
        # Also stop the content service
        self.content_service.stop_extraction()