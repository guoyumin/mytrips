"""
Classification Stage for Email Pipeline
"""
import logging
import threading
from typing import Dict, List, Optional

from backend.services.pipeline.base_stage import BasePipelineStage
from backend.services.email_classification_service import EmailClassificationService
from backend.database.models import Email, EmailContent
from backend.constants import TRAVEL_CATEGORIES

logger = logging.getLogger(__name__)


class ClassificationStage(BasePipelineStage):
    """Stage for classifying emails and forwarding travel emails"""
    
    def __init__(self, batch_size: int = 50):
        super().__init__("Classification", batch_size)
        
        # Initialize classification service
        self.classification_service = EmailClassificationService()
        
        # Track classification progress
        self.classification_started = False
        self.total_classified = 0
        self._progress_check_count = 0
    
    def check_pending_work(self) -> Optional[List[str]]:
        """Check for unclassified emails in database"""
        db = self.get_db_session()
        try:
            unclassified_count = db.query(Email).filter(
                Email.is_classified == False
            ).count()
            
            if unclassified_count > 0:
                logger.info(f"Found {unclassified_count} unclassified emails in database")
                return ["pending"]  # Return non-empty list to trigger processing
            
            return None
        finally:
            db.close()
    
    def process_batch(self, batch_data: Dict) -> Dict:
        """Process classification batch - mainly used for triggering classification start"""
        # This method is called by base class but we handle classification differently
        # We use the classification service which runs in its own thread
        return {}
    
    def run_classification(self, input_queue, output_queue):
        """
        Run the classification process
        
        Args:
            input_queue: Queue receiving email IDs from import stage
            output_queue: Queue to send travel emails to content extraction
        """
        try:
            self.start()
            
            # Don't automatically start classification on pending work
            # Wait for explicit signal from import stage
            logger.info("Classification stage ready, waiting for emails from import stage...")
            
            # Process incoming batches from import
            while not self.is_stopped():
                try:
                    # Get batch from import stage
                    batch = input_queue.get(timeout=1.0)
                    
                    # Check for end signal
                    if batch is None:
                        logger.info("Received end signal from import stage")
                        
                        # Check if we need to classify any remaining unclassified emails
                        if not self.classification_started:
                            if self.check_pending_work():
                                logger.info("Found unclassified emails after import completed")
                                self._start_classification()
                        
                        # Wait for classification to complete
                        if self.classification_started:
                            self._wait_for_classification_completion()
                            
                            # Send all travel emails to content extraction
                            logger.info("Classification completed, checking for all travel emails to send...")
                            self._send_all_travel_emails(output_queue)
                        
                        # Signal end to next stage
                        output_queue.put(None)
                        break
                    
                    # Start/restart classification as needed
                    if batch.get('batch_size', 0) > 0:
                        if not self.classification_started:
                            logger.info(f"Starting classification after receiving {batch['batch_size']} emails")
                            self._start_classification()
                        else:
                            # Check if previous classification finished
                            progress = self.classification_service.get_classification_progress()
                            if progress.get('finished', False):
                                logger.info("Restarting classification for newly imported emails")
                                self._start_classification()
                    
                except Exception as e:
                    if e.__class__.__name__ == 'Empty':  # queue.Empty
                        # Monitor classification progress and forward travel emails in real-time
                        if self.classification_started:
                            self._check_classification_progress(output_queue)
                        continue
                    else:
                        raise
            
            self.complete()
            
        except Exception as e:
            logger.error(f"Classification stage failed: {e}")
            self.fail(str(e))
            raise
    
    def _start_classification(self):
        """Start the classification service"""
        classification_result = self.classification_service.start_test_classification(limit=10000)
        
        if classification_result.get('started'):
            self.classification_started = True
            self.update_progress(0, 0, status='in_progress')
            logger.info("Classification service started successfully")
        else:
            raise Exception(f"Failed to start classification: {classification_result.get('message')}")
    
    def _wait_for_classification_completion(self):
        """Wait for classification to complete"""
        logger.info("Waiting for classification to complete...")
        
        while not self.is_stopped():
            progress = self.classification_service.get_classification_progress()
            
            # Update our progress
            self.update_progress(
                processed=progress.get('processed', 0),
                total=progress.get('total', 0),
                failed=progress.get('failed_count', 0),
                travel_count=progress.get('travel_count', 0)
            )
            
            if progress.get('finished', False):
                logger.info("Classification completed")
                break
            
            threading.Event().wait(1)
    
    def _check_classification_progress(self, output_queue):
        """Check classification progress and forward newly classified travel emails"""
        progress = self.classification_service.get_classification_progress()
        
        # Update our progress
        self.update_progress(
            processed=progress.get('processed', 0),
            total=progress.get('total', 0),
            failed=progress.get('failed_count', 0)
        )
        
        # Check for batch completion
        current_processed = progress.get('processed', 0)
        logger.debug(f"Classification progress check: {current_processed} processed, {self.total_classified} previously tracked")
        
        # Log every 5 checks to avoid spam
        self._progress_check_count += 1
        if self._progress_check_count % 5 == 0:
            logger.debug(f"Classification progress: {current_processed}/{progress.get('total', 0)}")
        
        # Check if new emails were classified
        if current_processed > self.total_classified:
            logger.info(f"New batch classified: {current_processed - self.total_classified} emails")
            
            # Get newly classified travel emails
            travel_emails = self._get_recent_travel_emails(current_processed - self.total_classified)
            
            if travel_emails:
                logger.info(f"Classification: Found {len(travel_emails)} newly classified travel emails")
                # Send to content extraction in batches
                batch_sent = 0
                for i in range(0, len(travel_emails), self.batch_size):
                    batch_ids = travel_emails[i:i+self.batch_size]
                    output_queue.put({
                        'email_ids': batch_ids,
                        'batch_size': len(batch_ids)
                    })
                    batch_sent += 1
                    logger.info(f"Classification: Sent batch {batch_sent} with {len(batch_ids)} travel emails to content extraction")
                
                logger.info(f"Classification: Total sent {len(travel_emails)} travel emails for content extraction")
            else:
                logger.debug("Classification: No travel emails found in this batch")
                
                # Update travel count
                self.update_progress(
                    processed=current_processed,
                    total=progress.get('total', 0),
                    travel_count=self.progress.get('travel_count', 0) + len(travel_emails)
                )
            
            self.total_classified = current_processed
    
    def _get_recent_travel_emails(self, limit: int) -> List[str]:
        """Get recently classified travel emails that need content extraction"""
        db = self.get_db_session()
        try:
            # First check how many travel emails exist in total
            total_travel = db.query(Email).filter(
                Email.classification.in_(TRAVEL_CATEGORIES),
                Email.is_classified == True
            ).count()
            logger.debug(f"Total travel emails in database: {total_travel}")
            
            # Get travel emails without content
            recent_travel_emails = db.query(Email.email_id).filter(
                Email.classification.in_(TRAVEL_CATEGORIES),
                Email.is_classified == True
            ).outerjoin(
                EmailContent, Email.email_id == EmailContent.email_id
            ).filter(
                EmailContent.email_id == None  # Not yet processed for content
            ).limit(limit).all()
            
            result = [email[0] for email in recent_travel_emails]
            logger.debug(f"Found {len(result)} travel emails needing content extraction (limit: {limit})")
            return result
        finally:
            db.close()
    
    def _send_all_travel_emails(self, output_queue):
        """Send all travel emails that need content extraction after classification completes"""
        db = self.get_db_session()
        try:
            # Only get travel emails that don't have content extracted yet
            travel_emails_needing_content = db.query(Email.email_id).filter(
                Email.classification.in_(TRAVEL_CATEGORIES)
            ).outerjoin(
                EmailContent, Email.email_id == EmailContent.email_id
            ).filter(
                EmailContent.email_id == None  # No content record exists
            ).all()
            
            if travel_emails_needing_content:
                travel_email_ids = [email[0] for email in travel_emails_needing_content]
                
                # Send in batches
                for i in range(0, len(travel_email_ids), self.batch_size):
                    batch_ids = travel_email_ids[i:i+self.batch_size]
                    output_queue.put({
                        'email_ids': batch_ids,
                        'batch_size': len(batch_ids)
                    })
                
                logger.info(f"Sent {len(travel_email_ids)} travel emails needing content extraction")
            else:
                logger.info("No travel emails need content extraction")
                
            # Get total travel count for progress
            total_travel = db.query(Email).filter(
                Email.classification.in_(TRAVEL_CATEGORIES)
            ).count()
            
            # Update final travel count
            self.update_progress(
                processed=self.progress['processed'],
                total=self.progress['total'],
                travel_count=total_travel
            )
        finally:
            db.close()
    
    def stop(self):
        """Stop classification stage"""
        super().stop()
        # Also stop the classification service
        self.classification_service.stop_classification()