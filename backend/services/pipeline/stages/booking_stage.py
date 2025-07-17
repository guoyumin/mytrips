"""
Booking Extraction Stage for Email Pipeline
"""
import logging
import threading
from typing import Dict, List, Optional
from sqlalchemy import and_

from backend.services.pipeline.base_stage import BasePipelineStage
from backend.services.email_booking_extraction_service import EmailBookingExtractionService
from backend.database.models import Email, EmailContent, TransportSegment, Accommodation, TourActivity, Cruise
from backend.constants import TRAVEL_CATEGORIES

logger = logging.getLogger(__name__)


class BookingExtractionStage(BasePipelineStage):
    """Stage for extracting booking information from emails with content"""
    
    def __init__(self, batch_size: int = 10):
        super().__init__("Booking Extraction", batch_size)
        
        # Initialize booking service
        self.booking_service = EmailBookingExtractionService()
        
        # Track extracted emails and bookings
        self.booking_extracted_emails = set()
        self.total_bookings_found = 0
        self.extraction_started = False
    
    def check_pending_work(self) -> Optional[List[str]]:
        """Check for emails with content that need booking extraction"""
        db = self.get_db_session()
        try:
            pending_emails = db.query(EmailContent.email_id).filter(
                and_(
                    EmailContent.extraction_status == 'completed',
                    EmailContent.booking_extraction_status.in_(['pending', 'failed'])
                )
            ).join(
                Email, EmailContent.email_id == Email.email_id
            ).filter(
                Email.classification.in_(TRAVEL_CATEGORIES)
            ).all()
            
            if pending_emails:
                email_ids = [email[0] for email in pending_emails]
                logger.info(f"Found {len(email_ids)} emails pending booking extraction")
                return email_ids
            
            return None
        finally:
            db.close()
    
    def process_batch(self, batch_data: Dict) -> Dict:
        """Process a batch of emails for booking extraction"""
        email_ids = batch_data.get('email_ids', [])
        
        if not email_ids:
            return {}
        
        logger.info(f"Starting booking extraction for {len(email_ids)} emails")
        
        # Start extraction using the service
        extraction_result = self.booking_service.start_extraction(email_ids=email_ids)
        
        if not extraction_result.get('started'):
            logger.error(f"Failed to start booking extraction: {extraction_result.get('message')}")
            return {}
        
        self.extraction_started = True
        
        # Monitor extraction progress
        logger.info(f"Booking extraction: Monitoring extraction progress for {len(email_ids)} emails")
        check_count = 0
        while not self.is_stopped():
            progress = self.booking_service.get_extraction_progress()
            check_count += 1
            
            # Log progress every 5 checks
            if check_count % 5 == 0:
                logger.info(f"Booking extraction progress: {progress.get('extracted_count', 0)}/{progress.get('total_emails', 0)} extracted, {progress.get('failed_count', 0)} failed")
            
            # Update our progress
            self.update_progress(
                processed=len(self.booking_extracted_emails) + progress.get('extracted_count', 0),
                total=self.progress.get('total', 0) + len(email_ids),
                failed=progress.get('failed_count', 0),
                bookings_found=self.total_bookings_found
            )
            
            # Track successfully extracted emails
            self.booking_extracted_emails.update(email_ids[:progress.get('extracted_count', 0)])
            
            # Check if extraction is finished
            if progress.get('finished', False):
                logger.info("Booking extraction batch completed")
                
                # Count bookings found in this batch
                bookings_count = self._count_bookings_in_batch(email_ids)
                self.total_bookings_found += bookings_count
                
                self.update_progress(
                    processed=len(self.booking_extracted_emails),
                    total=self.progress.get('total', 0),
                    bookings_found=self.total_bookings_found
                )
                
                logger.info(f"Found {bookings_count} bookings in this batch (total: {self.total_bookings_found})")
                break
            
            # Wait before checking again
            threading.Event().wait(1)
        
        return {}
    
    def run_extraction(self, input_queue, output_queue=None):
        """
        Run the booking extraction process
        
        Args:
            input_queue: Queue receiving email IDs from content extraction
            output_queue: Not used (booking is the final stage)
        """
        try:
            self.start()
            
            # Check for pending work but don't process it automatically
            # Only process if explicitly requested by pipeline
            pending_work = self.check_pending_work()
            if pending_work:
                logger.info(f"Booking extraction: Found {len(pending_work)} pending emails in database")
                # Process pending emails in batches
                for i in range(0, len(pending_work), self.batch_size):
                    if self.is_stopped():
                        break
                    
                    batch_ids = pending_work[i:i+self.batch_size]
                    logger.info(f"Booking extraction: Processing pending batch with {len(batch_ids)} emails")
                    self.process_batch({'email_ids': batch_ids, 'batch_size': len(batch_ids)})
            else:
                logger.info("Booking extraction stage ready, no pending emails found")
            
            # Process incoming batches
            logger.info("Booking extraction stage: Starting to process incoming batches from content extraction")
            batch_count = 0
            while not self.is_stopped():
                try:
                    # Get batch from content extraction stage
                    logger.debug("Booking extraction: Waiting for batch from content queue...")
                    batch = input_queue.get(timeout=1.0)
                    
                    # Check for end signal
                    if batch is None:
                        logger.info("Booking extraction: Received end signal from content extraction stage")
                        
                        # Wait for any ongoing extraction to complete
                        if self.extraction_started:
                            logger.info("Booking extraction: Waiting for ongoing extraction to complete...")
                            wait_count = 0
                            while not self.is_stopped():
                                progress = self.booking_service.get_extraction_progress()
                                wait_count += 1
                                if wait_count % 5 == 0:  # Log every 5 seconds
                                    logger.info(f"Booking extraction: Still waiting... Progress: {progress.get('extracted_count', 0)}/{progress.get('total', 0)}")
                                if progress.get('finished', False):
                                    logger.info("Booking extraction: Extraction finished")
                                    break
                                threading.Event().wait(1)
                        
                        break
                    
                    batch_count += 1
                    logger.info(f"Booking extraction: Received batch #{batch_count} with {batch.get('batch_size', 0)} emails")
                    
                    # Process the batch
                    self.process_batch(batch)
                    
                except Exception as e:
                    if e.__class__.__name__ == 'Empty':  # queue.Empty
                        continue
                    else:
                        logger.error(f"Booking extraction: Error processing batch - {e}")
                        raise
            
            self.complete()
            logger.info(f"Booking extraction completed. Total bookings found: {self.total_bookings_found}")
            
        except Exception as e:
            logger.error(f"Booking extraction stage failed: {e}")
            self.fail(str(e))
            raise
    
    def _count_bookings_in_batch(self, email_ids: List[str]) -> int:
        """Count bookings found in a batch of emails"""
        db = self.get_db_session()
        try:
            # Count bookings from extracted emails
            transport_count = 0
            accommodation_count = 0
            tour_count = 0
            cruise_count = 0
            
            # Get all transport segments and check their emails
            transports = db.query(TransportSegment).all()
            for transport in transports:
                if any(email.email_id in email_ids for email in transport.emails):
                    transport_count += 1
            
            # Get all accommodations and check their emails
            accommodations = db.query(Accommodation).all()
            for accommodation in accommodations:
                if any(email.email_id in email_ids for email in accommodation.emails):
                    accommodation_count += 1
            
            # Get all tours and check their emails
            tours = db.query(TourActivity).all()
            for tour in tours:
                if any(email.email_id in email_ids for email in tour.emails):
                    tour_count += 1
            
            # Get all cruises and check their emails
            cruises = db.query(Cruise).all()
            for cruise in cruises:
                if any(email.email_id in email_ids for email in cruise.emails):
                    cruise_count += 1
            
            total_bookings = transport_count + accommodation_count + tour_count + cruise_count
            
            if total_bookings > 0:
                logger.info(f"Bookings found - Transport: {transport_count}, Accommodation: {accommodation_count}, Tour: {tour_count}, Cruise: {cruise_count}")
            
            return total_bookings
            
        finally:
            db.close()
    
    def stop(self):
        """Stop booking extraction stage"""
        super().stop()
        # Also stop the booking service
        self.booking_service.stop_extraction()