"""
Email Pipeline Service - Full pipeline processing with parallel execution
Processes emails through: Import → Classification → Content Extraction → Booking Extraction
"""
import logging
import threading
import queue
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from backend.services.email_cache_service import EmailCacheService
from backend.services.email_classification_service import EmailClassificationService
from backend.services.email_content_service import EmailContentService
from backend.services.email_booking_extraction_service import EmailBookingExtractionService
from backend.database.config import SessionLocal
from backend.database.models import Email, EmailContent
from backend.constants import TRAVEL_CATEGORIES

logger = logging.getLogger(__name__)


class EmailPipelineService:
    """Service for running the complete email processing pipeline with parallel execution"""
    
    def __init__(self):
        """Initialize all required services"""
        try:
            # Initialize services
            self.email_cache_service = EmailCacheService()
            self.classification_service = EmailClassificationService()
            self.content_service = EmailContentService()
            self.booking_service = EmailBookingExtractionService()
            
            logger.info("Email pipeline service initialized with all required services")
        except Exception as e:
            logger.error(f"Failed to initialize email pipeline service: {e}")
            raise
        
        # Pipeline state tracking
        self.pipeline_state = {
            'is_running': False,
            'current_stage': None,  # 'import', 'classification', 'content', 'booking'
            'date_range': None,
            'start_time': None,
            'end_time': None,
            'stages': {
                'import': {
                    'status': 'pending',  # pending, in_progress, completed, failed
                    'progress': 0,
                    'total': 0,
                    'processed': 0,
                    'failed': 0,
                    'start_time': None,
                    'end_time': None
                },
                'classification': {
                    'status': 'pending',
                    'progress': 0,
                    'total': 0,
                    'processed': 0,
                    'failed': 0,
                    'travel_count': 0,
                    'start_time': None,
                    'end_time': None
                },
                'content': {
                    'status': 'pending',
                    'progress': 0,
                    'total': 0,
                    'processed': 0,
                    'failed': 0,
                    'start_time': None,
                    'end_time': None
                },
                'booking': {
                    'status': 'pending',
                    'progress': 0,
                    'total': 0,
                    'processed': 0,
                    'failed': 0,
                    'bookings_found': 0,
                    'start_time': None,
                    'end_time': None
                }
            },
            'errors': [],
            'message': ''
        }
        
        # Threading control
        self._stop_flag = threading.Event()
        self._pipeline_thread = None
        self._lock = threading.Lock()
        
        # Queues for parallel processing
        self._import_queue = queue.Queue(maxsize=10)  # Limit queue size to control memory
        self._classification_queue = queue.Queue(maxsize=10)
        self._content_queue = queue.Queue(maxsize=10)
        self._booking_queue = queue.Queue(maxsize=10)
        
        # Batch processing configuration
        self.batch_sizes = {
            'import': 100,  # Import 100 emails at a time
            'classification': 50,  # Classify 50 emails at a time
            'content': 20,  # Extract content for 20 emails at a time
            'booking': 10   # Extract bookings for 10 emails at a time
        }
    
    def start_pipeline(self, date_range: Dict) -> Dict:
        """
        Start the email processing pipeline
        
        Args:
            date_range: Dictionary with 'start_date' and 'end_date' keys
            
        Returns:
            Dictionary with start status
        """
        with self._lock:
            # Check if pipeline is already running
            if self.pipeline_state['is_running']:
                return {
                    'started': False,
                    'message': 'Pipeline is already running'
                }
            
            # Validate date range
            if not date_range or 'start_date' not in date_range or 'end_date' not in date_range:
                return {
                    'started': False,
                    'message': 'Invalid date range. Must provide start_date and end_date'
                }
            
            # Reset pipeline state
            self._reset_pipeline_state()
            self._stop_flag.clear()
            
            # Set pipeline parameters
            self.pipeline_state['is_running'] = True
            self.pipeline_state['date_range'] = date_range
            self.pipeline_state['start_time'] = datetime.now()
            self.pipeline_state['message'] = 'Pipeline started'
            
            # Start pipeline thread
            self._pipeline_thread = threading.Thread(
                target=self._run_pipeline,
                args=(date_range,),
                daemon=True
            )
            self._pipeline_thread.start()
            
            logger.info(f"Started email pipeline for date range: {date_range['start_date']} to {date_range['end_date']}")
            
            return {
                'started': True,
                'message': f"Pipeline started for emails from {date_range['start_date']} to {date_range['end_date']}"
            }
    
    def stop_pipeline(self) -> Dict:
        """Stop the running pipeline"""
        with self._lock:
            if not self.pipeline_state['is_running']:
                return {
                    'stopped': False,
                    'message': 'Pipeline is not running'
                }
            
            # Set stop flag
            self._stop_flag.set()
            self.pipeline_state['message'] = 'Pipeline stop requested'
            
            # Stop all running services
            self.email_cache_service.stop_import()
            self.classification_service.stop_classification()
            self.content_service.stop_extraction()
            self.booking_service.stop_extraction()
            
            logger.info("Pipeline stop requested")
            
            return {
                'stopped': True,
                'message': 'Pipeline stop requested. Current operations will complete before stopping.'
            }
    
    def get_pipeline_progress(self) -> Dict:
        """Get current pipeline progress"""
        with self._lock:
            progress = self.pipeline_state.copy()
            
            # Calculate overall progress
            total_weight = 100
            stage_weights = {
                'import': 25,
                'classification': 25,
                'content': 25,
                'booking': 25
            }
            
            overall_progress = 0
            for stage, weight in stage_weights.items():
                stage_progress = self.pipeline_state['stages'][stage]['progress']
                overall_progress += (stage_progress * weight) / 100
            
            progress['overall_progress'] = int(overall_progress)
            
            # Add elapsed time
            if self.pipeline_state['start_time']:
                if self.pipeline_state['end_time']:
                    elapsed = (self.pipeline_state['end_time'] - self.pipeline_state['start_time']).total_seconds()
                else:
                    elapsed = (datetime.now() - self.pipeline_state['start_time']).total_seconds()
                progress['elapsed_time'] = int(elapsed)
            
            return progress
    
    def _reset_pipeline_state(self):
        """Reset pipeline state to initial values"""
        for stage in self.pipeline_state['stages'].values():
            stage.update({
                'status': 'pending',
                'progress': 0,
                'total': 0,
                'processed': 0,
                'failed': 0,
                'start_time': None,
                'end_time': None
            })
        
        self.pipeline_state.update({
            'is_running': False,
            'current_stage': None,
            'date_range': None,
            'start_time': None,
            'end_time': None,
            'errors': [],
            'message': ''
        })
        
        # Clear queues
        self._clear_queues()
    
    def _clear_queues(self):
        """Clear all processing queues"""
        for q in [self._import_queue, self._classification_queue, self._content_queue, self._booking_queue]:
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
    
    def _run_pipeline(self, date_range: Dict):
        """
        Main pipeline execution logic with parallel processing
        
        Args:
            date_range: Dictionary with date range for import
        """
        try:
            logger.info("Starting pipeline execution")
            
            # Use ThreadPoolExecutor for parallel execution
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                # Start all pipeline stages
                futures = []
                
                # Stage 1: Import with immediate classification
                import_future = executor.submit(
                    self._import_with_classification_stage,
                    date_range
                )
                futures.append(import_future)
                
                # Stage 1.5: Process classification in parallel with import
                classification_future = executor.submit(
                    self._classification_processing_stage
                )
                futures.append(classification_future)
                
                # Stage 2: Content extraction for classified travel emails
                content_future = executor.submit(
                    self._content_extraction_stage
                )
                futures.append(content_future)
                
                # Stage 3: Booking extraction for emails with content
                booking_future = executor.submit(
                    self._booking_extraction_stage
                )
                futures.append(booking_future)
                
                # Wait for all stages to complete or stop
                concurrent.futures.wait(futures)
                
                # Check if all completed successfully
                success = all(not future.exception() for future in futures)
                
                if success and not self._stop_flag.is_set():
                    self.pipeline_state['message'] = 'Pipeline completed successfully'
                    logger.info("Pipeline completed successfully")
                elif self._stop_flag.is_set():
                    self.pipeline_state['message'] = 'Pipeline stopped by user'
                    logger.info("Pipeline stopped by user")
                else:
                    self.pipeline_state['message'] = 'Pipeline completed with errors'
                    logger.error("Pipeline completed with errors")
                
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            self.pipeline_state['message'] = f'Pipeline failed: {str(e)}'
            self.pipeline_state['errors'].append({
                'stage': 'pipeline',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        finally:
            with self._lock:
                self.pipeline_state['is_running'] = False
                self.pipeline_state['end_time'] = datetime.now()
                self.pipeline_state['current_stage'] = None
    
    def _import_with_classification_stage(self, date_range: Dict):
        """Stage 1: Import emails and immediately send for classification"""
        try:
            # Update stage status
            with self._lock:
                self.pipeline_state['current_stage'] = 'import'
                self.pipeline_state['stages']['import']['status'] = 'in_progress'
                self.pipeline_state['stages']['import']['start_time'] = datetime.now()
            
            logger.info(f"Starting import stage for date range: {date_range}")
            
            # Start import process
            import_result = self.email_cache_service.start_import(
                start_date=date_range['start_date'],
                end_date=date_range['end_date'],
                limit=None  # No limit, import all in date range
            )
            
            if not import_result.get('started'):
                raise Exception(f"Failed to start import: {import_result.get('message')}")
            
            # Monitor import progress and send batches for classification
            last_processed_count = 0
            classification_started = False
            
            while not self._stop_flag.is_set():
                # Get import progress
                import_progress = self.email_cache_service.get_import_progress()
                
                # Update import stage progress
                with self._lock:
                    self.pipeline_state['stages']['import'].update({
                        'progress': import_progress.get('progress', 0),
                        'total': import_progress.get('total', 0),
                        'processed': import_progress.get('imported', 0),
                        'failed': import_progress.get('failed', 0)
                    })
                
                # Check if we have new emails to classify
                current_imported = import_progress.get('imported', 0)
                new_emails_count = current_imported - last_processed_count
                
                if new_emails_count >= self.batch_sizes['classification']:
                    # Get the newly imported email IDs
                    db = SessionLocal()
                    try:
                        # Get emails imported since last check
                        new_emails = db.query(Email.email_id).filter(
                            Email.timestamp >= date_range['start_date'],
                            Email.timestamp <= date_range['end_date']
                        ).order_by(Email.imported_at.desc()).limit(new_emails_count).all()
                        
                        email_ids = [email[0] for email in new_emails]
                        
                        if email_ids:
                            # Put email IDs in classification queue
                            self._classification_queue.put({
                                'email_ids': email_ids,
                                'batch_size': len(email_ids)
                            })
                            
                            # Start classification if not already started
                            if not classification_started:
                                with self._lock:
                                    self.pipeline_state['stages']['classification']['status'] = 'in_progress'
                                    self.pipeline_state['stages']['classification']['start_time'] = datetime.now()
                                classification_started = True
                            
                            logger.info(f"Sent {len(email_ids)} emails for classification")
                            last_processed_count = current_imported
                            
                    finally:
                        db.close()
                
                # Check if import is finished
                if import_progress.get('finished', False):
                    # Send any remaining emails for classification
                    if current_imported > last_processed_count:
                        db = SessionLocal()
                        try:
                            remaining_count = current_imported - last_processed_count
                            remaining_emails = db.query(Email.email_id).filter(
                                Email.timestamp >= date_range['start_date'],
                                Email.timestamp <= date_range['end_date']
                            ).order_by(Email.imported_at.desc()).limit(remaining_count).all()
                            
                            email_ids = [email[0] for email in remaining_emails]
                            
                            if email_ids:
                                self._classification_queue.put({
                                    'email_ids': email_ids,
                                    'batch_size': len(email_ids)
                                })
                                logger.info(f"Sent final {len(email_ids)} emails for classification")
                                
                        finally:
                            db.close()
                    
                    # Signal end of import
                    self._classification_queue.put(None)  # Sentinel value
                    
                    with self._lock:
                        self.pipeline_state['stages']['import']['status'] = 'completed'
                        self.pipeline_state['stages']['import']['end_time'] = datetime.now()
                        self.pipeline_state['stages']['import']['progress'] = 100
                    
                    logger.info(f"Import stage completed. Total imported: {current_imported}")
                    break
                
                # Wait before checking again
                threading.Event().wait(2)  # Check every 2 seconds
                
        except Exception as e:
            logger.error(f"Import stage failed: {e}")
            with self._lock:
                self.pipeline_state['stages']['import']['status'] = 'failed'
                self.pipeline_state['stages']['import']['end_time'] = datetime.now()
                self.pipeline_state['errors'].append({
                    'stage': 'import',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
            raise
    
    def _classification_processing_stage(self):
        """Process classification requests from import stage"""
        try:
            logger.info("Starting classification processing stage")
            
            # Track classified emails to send to content extraction
            classified_travel_emails = set()
            total_classified = 0
            classification_started = False
            
            while not self._stop_flag.is_set():
                try:
                    # Get classification batch from queue (with timeout to check stop flag)
                    batch = self._classification_queue.get(timeout=1)
                    
                    # Check for sentinel value (import finished)
                    if batch is None:
                        logger.info("Received end signal from import stage")
                        
                        # Wait for any ongoing classification to complete
                        if classification_started:
                            while not self._stop_flag.is_set():
                                progress = self.classification_service.get_classification_progress()
                                if progress.get('finished', False):
                                    break
                                threading.Event().wait(1)
                        
                        # Signal content extraction that classification is done
                        self._content_queue.put(None)
                        break
                    
                    # For now, we'll start classification once after a certain number of imports
                    # This is because the current classification service doesn't support email IDs
                    # In the future, we should enhance it to accept specific email IDs
                    
                    if not classification_started and self.pipeline_state['stages']['import']['processed'] >= 100:
                        # Start classification for all unclassified emails
                        logger.info("Starting classification for imported emails")
                        
                        classification_result = self.classification_service.start_test_classification(limit=10000)
                        
                        if not classification_result.get('started'):
                            logger.error(f"Failed to start classification: {classification_result.get('message')}")
                            continue
                        
                        classification_started = True
                    
                except queue.Empty:
                    # Check classification progress if running
                    if classification_started:
                        progress = self.classification_service.get_classification_progress()
                        
                        # Update classification stage progress
                        with self._lock:
                            self.pipeline_state['stages']['classification'].update({
                                'progress': progress.get('progress', 0),
                                'total': progress.get('total', 0),
                                'processed': progress.get('processed', 0),
                                'failed': progress.get('failed_count', 0)
                            })
                        
                        # Get newly classified travel emails
                        if progress.get('processed', 0) > total_classified:
                            # Query database for newly classified travel emails
                            db = SessionLocal()
                            try:
                                new_travel_emails = db.query(Email.email_id).filter(
                                    Email.classification.in_(TRAVEL_CATEGORIES),
                                    ~Email.email_id.in_(classified_travel_emails)
                                ).limit(self.batch_sizes['content']).all()
                                
                                if new_travel_emails:
                                    travel_email_ids = [email[0] for email in new_travel_emails]
                                    classified_travel_emails.update(travel_email_ids)
                                    
                                    # Send to content extraction
                                    self._content_queue.put({
                                        'email_ids': travel_email_ids,
                                        'batch_size': len(travel_email_ids)
                                    })
                                    
                                    with self._lock:
                                        self.pipeline_state['stages']['classification']['travel_count'] = len(classified_travel_emails)
                                    
                                    logger.info(f"Sent {len(travel_email_ids)} travel emails for content extraction")
                                
                                total_classified = progress.get('processed', 0)
                                
                            finally:
                                db.close()
                    
                    continue
                    
                except Exception as e:
                    logger.error(f"Error in classification processing: {e}")
                    self.pipeline_state['errors'].append({
                        'stage': 'classification',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Mark classification as completed
            with self._lock:
                self.pipeline_state['stages']['classification']['status'] = 'completed'
                self.pipeline_state['stages']['classification']['end_time'] = datetime.now()
                if self.pipeline_state['stages']['classification']['total'] > 0:
                    self.pipeline_state['stages']['classification']['progress'] = 100
            
            logger.info("Classification processing stage completed")
            
        except Exception as e:
            logger.error(f"Classification stage failed: {e}")
            with self._lock:
                self.pipeline_state['stages']['classification']['status'] = 'failed'
                self.pipeline_state['stages']['classification']['end_time'] = datetime.now()
                self.pipeline_state['errors'].append({
                    'stage': 'classification',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
            raise
    
    def _content_extraction_stage(self):
        """Stage 2: Extract content for classified travel emails"""
        try:
            logger.info("Starting content extraction stage")
            
            # Track extracted emails to send to booking extraction
            content_extracted_emails = set()
            content_started = False
            
            with self._lock:
                self.pipeline_state['stages']['content']['status'] = 'in_progress'
                self.pipeline_state['stages']['content']['start_time'] = datetime.now()
            
            while not self._stop_flag.is_set():
                try:
                    # Get content extraction batch from queue
                    batch = self._content_queue.get(timeout=1)
                    
                    # Check for sentinel value (classification finished)
                    if batch is None:
                        logger.info("Received end signal from classification stage")
                        
                        # Wait for any ongoing content extraction to complete
                        if content_started:
                            while not self._stop_flag.is_set():
                                progress = self.content_service.get_extraction_progress()
                                if progress.get('finished', False):
                                    break
                                threading.Event().wait(1)
                        
                        # Signal booking extraction that content extraction is done
                        self._booking_queue.put(None)
                        break
                    
                    email_ids = batch['email_ids']
                    
                    # Start content extraction for these emails
                    logger.info(f"Starting content extraction for {len(email_ids)} travel emails")
                    
                    extraction_result = self.content_service.start_extraction(email_ids=email_ids)
                    
                    if not extraction_result.get('started'):
                        logger.error(f"Failed to start content extraction: {extraction_result.get('message')}")
                        continue
                    
                    content_started = True
                    
                    # Monitor extraction progress
                    last_extracted_count = 0
                    
                    while not self._stop_flag.is_set():
                        progress = self.content_service.get_extraction_progress()
                        
                        # Update content stage progress
                        with self._lock:
                            travel_count = self.pipeline_state['stages']['classification']['travel_count']
                            extracted_count = len(content_extracted_emails) + progress.get('extracted_count', 0)
                            
                            self.pipeline_state['stages']['content'].update({
                                'progress': int((extracted_count / travel_count * 100)) if travel_count > 0 else 0,
                                'total': travel_count,
                                'processed': extracted_count,
                                'failed': progress.get('failed_count', 0)
                            })
                        
                        # Check for newly extracted emails
                        current_extracted = progress.get('extracted_count', 0)
                        if current_extracted > last_extracted_count:
                            # Query database for emails with extracted content
                            db = SessionLocal()
                            try:
                                new_extracted_emails = db.query(EmailContent.email_id).filter(
                                    EmailContent.email_id.in_(email_ids),
                                    EmailContent.extraction_status == 'completed',
                                    ~EmailContent.email_id.in_(content_extracted_emails)
                                ).limit(self.batch_sizes['booking']).all()
                                
                                if new_extracted_emails:
                                    extracted_email_ids = [email[0] for email in new_extracted_emails]
                                    content_extracted_emails.update(extracted_email_ids)
                                    
                                    # Send to booking extraction
                                    self._booking_queue.put({
                                        'email_ids': extracted_email_ids,
                                        'batch_size': len(extracted_email_ids)
                                    })
                                    
                                    logger.info(f"Sent {len(extracted_email_ids)} emails for booking extraction")
                                
                                last_extracted_count = current_extracted
                                
                            finally:
                                db.close()
                        
                        # Check if extraction is finished
                        if progress.get('finished', False):
                            logger.info("Content extraction batch completed")
                            break
                        
                        # Wait before checking again
                        threading.Event().wait(1)
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error in content extraction processing: {e}")
                    self.pipeline_state['errors'].append({
                        'stage': 'content',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Mark content extraction as completed
            with self._lock:
                self.pipeline_state['stages']['content']['status'] = 'completed'
                self.pipeline_state['stages']['content']['end_time'] = datetime.now()
                if self.pipeline_state['stages']['content']['total'] > 0:
                    self.pipeline_state['stages']['content']['progress'] = 100
            
            logger.info("Content extraction stage completed")
            
        except Exception as e:
            logger.error(f"Content extraction stage failed: {e}")
            with self._lock:
                self.pipeline_state['stages']['content']['status'] = 'failed'
                self.pipeline_state['stages']['content']['end_time'] = datetime.now()
                self.pipeline_state['errors'].append({
                    'stage': 'content',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
            raise
    
    def _booking_extraction_stage(self):
        """Stage 3: Extract bookings from emails with content"""
        try:
            logger.info("Starting booking extraction stage")
            
            # Track booking extraction progress
            booking_extracted_emails = set()
            booking_started = False
            total_bookings_found = 0
            
            with self._lock:
                self.pipeline_state['stages']['booking']['status'] = 'in_progress'
                self.pipeline_state['stages']['booking']['start_time'] = datetime.now()
            
            while not self._stop_flag.is_set():
                try:
                    # Get booking extraction batch from queue
                    batch = self._booking_queue.get(timeout=1)
                    
                    # Check for sentinel value (content extraction finished)
                    if batch is None:
                        logger.info("Received end signal from content extraction stage")
                        
                        # Wait for any ongoing booking extraction to complete
                        if booking_started:
                            while not self._stop_flag.is_set():
                                progress = self.booking_service.get_extraction_progress()
                                if progress.get('finished', False):
                                    break
                                threading.Event().wait(1)
                        
                        break
                    
                    email_ids = batch['email_ids']
                    
                    # Start booking extraction for these emails
                    logger.info(f"Starting booking extraction for {len(email_ids)} emails")
                    
                    extraction_result = self.booking_service.start_extraction(email_ids=email_ids)
                    
                    if not extraction_result.get('started'):
                        logger.error(f"Failed to start booking extraction: {extraction_result.get('message')}")
                        continue
                    
                    booking_started = True
                    
                    # Monitor extraction progress
                    while not self._stop_flag.is_set():
                        progress = self.booking_service.get_extraction_progress()
                        
                        # Update booking stage progress
                        with self._lock:
                            content_count = self.pipeline_state['stages']['content']['processed']
                            extracted_count = len(booking_extracted_emails) + progress.get('extracted_count', 0)
                            
                            self.pipeline_state['stages']['booking'].update({
                                'progress': int((extracted_count / content_count * 100)) if content_count > 0 else 0,
                                'total': content_count,
                                'processed': extracted_count,
                                'failed': progress.get('failed_count', 0),
                                'bookings_found': total_bookings_found
                            })
                        
                        # Track successfully extracted emails
                        booking_extracted_emails.update(email_ids[:progress.get('extracted_count', 0)])
                        
                        # Check if extraction is finished
                        if progress.get('finished', False):
                            logger.info("Booking extraction batch completed")
                            
                            # Query database to count bookings found
                            db = SessionLocal()
                            try:
                                from backend.database.models import TransportSegment, Accommodation, TourActivity, Cruise
                                
                                # Count bookings from extracted emails
                                # For many-to-many relationships, we need to check if any related email matches
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
                                
                                batch_bookings = transport_count + accommodation_count + tour_count + cruise_count
                                total_bookings_found += batch_bookings
                                
                                with self._lock:
                                    self.pipeline_state['stages']['booking']['bookings_found'] = total_bookings_found
                                
                                logger.info(f"Found {batch_bookings} bookings in this batch (total: {total_bookings_found})")
                                
                            finally:
                                db.close()
                            
                            break
                        
                        # Wait before checking again
                        threading.Event().wait(1)
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error in booking extraction processing: {e}")
                    self.pipeline_state['errors'].append({
                        'stage': 'booking',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Mark booking extraction as completed
            with self._lock:
                self.pipeline_state['stages']['booking']['status'] = 'completed'
                self.pipeline_state['stages']['booking']['end_time'] = datetime.now()
                if self.pipeline_state['stages']['booking']['total'] > 0:
                    self.pipeline_state['stages']['booking']['progress'] = 100
            
            logger.info(f"Booking extraction stage completed. Total bookings found: {total_bookings_found}")
            
        except Exception as e:
            logger.error(f"Booking extraction stage failed: {e}")
            with self._lock:
                self.pipeline_state['stages']['booking']['status'] = 'failed'
                self.pipeline_state['stages']['booking']['end_time'] = datetime.now()
                self.pipeline_state['errors'].append({
                    'stage': 'booking',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
            raise