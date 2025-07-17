"""
Base Stage for Pipeline Processing
"""
import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional, Any, List
import queue

from backend.database.config import SessionLocal

logger = logging.getLogger(__name__)


class BasePipelineStage(ABC):
    """Base class for pipeline stages with common functionality"""
    
    def __init__(self, stage_name: str, batch_size: int = 20):
        self.stage_name = stage_name
        self.batch_size = batch_size
        self.progress = {
            'status': 'pending',
            'progress': 0,
            'total': 0,
            'processed': 0,
            'failed': 0,
            'start_time': None,
            'end_time': None
        }
        self._lock = threading.Lock()
        self._stop_flag = threading.Event()
    
    @abstractmethod
    def process_batch(self, batch_data: Dict) -> Dict:
        """Process a single batch of data"""
        pass
    
    @abstractmethod
    def check_pending_work(self) -> Optional[List[str]]:
        """Check database for any pending work at startup"""
        pass
    
    def start(self):
        """Start the stage processing"""
        # Clear the stop flag when starting
        self._stop_flag.clear()
        with self._lock:
            self.progress['status'] = 'in_progress'
            self.progress['start_time'] = datetime.now()
        logger.info(f"Starting {self.stage_name} stage")
    
    def stop(self):
        """Stop the stage processing"""
        logger.info(f"Stop requested for {self.stage_name} stage - setting stop flag")
        self._stop_flag.set()
        logger.info(f"Stop flag set for {self.stage_name} stage - is_stopped: {self.is_stopped()}")
    
    def complete(self):
        """Mark stage as completed"""
        with self._lock:
            self.progress['status'] = 'completed'
            self.progress['end_time'] = datetime.now()
            self.progress['progress'] = 100
        logger.info(f"{self.stage_name} stage completed")
    
    def fail(self, error: str):
        """Mark stage as failed"""
        with self._lock:
            self.progress['status'] = 'failed'
            self.progress['end_time'] = datetime.now()
        logger.error(f"{self.stage_name} stage failed: {error}")
    
    def update_progress(self, processed: int, total: int, failed: int = 0, **kwargs):
        """Update stage progress with additional custom fields"""
        with self._lock:
            self.progress['processed'] = processed
            self.progress['total'] = total
            self.progress['failed'] = failed
            if total > 0:
                self.progress['progress'] = int((processed / total) * 100)
            
            # Update any additional fields
            for key, value in kwargs.items():
                self.progress[key] = value
    
    def get_progress(self) -> Dict:
        """Get current progress"""
        with self._lock:
            return self.progress.copy()
    
    def is_stopped(self) -> bool:
        """Check if stop was requested"""
        return self._stop_flag.is_set()
    
    def get_db_session(self):
        """Get a database session"""
        return SessionLocal()
    
    def process_queue(self, input_queue: queue.Queue, output_queue: Optional[queue.Queue] = None):
        """
        Generic queue processing logic
        
        Args:
            input_queue: Queue to read from
            output_queue: Optional queue to write results to
        """
        try:
            self.start()
            
            # Check for pending work first
            pending_work = self.check_pending_work()
            if pending_work:
                logger.info(f"{self.stage_name}: Found {len(pending_work)} pending items at startup")
                # Process pending work in batches
                for i in range(0, len(pending_work), self.batch_size):
                    if self.is_stopped():
                        break
                    batch = pending_work[i:i+self.batch_size]
                    result = self.process_batch({'email_ids': batch, 'batch_size': len(batch)})
                    if output_queue and result:
                        output_queue.put(result)
            
            # Process queue items
            while not self.is_stopped():
                try:
                    # Get item from queue with timeout
                    item = input_queue.get(timeout=1.0)
                    
                    # Check for end signal
                    if item is None:
                        logger.info(f"{self.stage_name}: Received end signal")
                        break
                    
                    # Process the batch
                    result = self.process_batch(item)
                    
                    # Send result to next stage if applicable
                    if output_queue and result:
                        output_queue.put(result)
                        
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"{self.stage_name}: Error processing batch: {e}")
                    self.update_progress(
                        self.progress['processed'],
                        self.progress['total'],
                        self.progress['failed'] + 1
                    )
            
            # Send end signal to next stage
            if output_queue:
                output_queue.put(None)
            
            self.complete()
            
        except Exception as e:
            logger.error(f"{self.stage_name} failed: {e}")
            self.fail(str(e))
            raise