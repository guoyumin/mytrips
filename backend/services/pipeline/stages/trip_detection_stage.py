"""
Trip Detection Stage for Email Pipeline
"""
import logging
import threading
import time
from typing import Dict, List, Optional

from backend.services.pipeline.base_stage import BasePipelineStage
from backend.services.trip_detection_service import TripDetectionService

logger = logging.getLogger(__name__)


class TripDetectionStage(BasePipelineStage):
    """Stage for detecting trips from extracted booking information"""
    
    def __init__(self, batch_size: int = 10):
        super().__init__("Trip Detection", batch_size)
        
        # Initialize service
        self.trip_service = TripDetectionService()
        self.detection_started = False
    
    def check_pending_work(self) -> Optional[List[str]]:
        """Check for pending work - not used in this stage's current implementation"""
        return None

    def process_batch(self, batch_data: Dict) -> Dict:
        """Process a batch - not used in this stage's current implementation"""
        return {}
    
    def run_detection(self, date_range: Dict):
        """
        Run the trip detection process
        
        Args:
            date_range: Date range for detection
        """
        try:
            self.start()
            logger.info("Trip Detection Stage: Starting detection process")
            
            # Start detection using the service
            result = self.trip_service.start_detection(date_range)
            
            if not result.get('started'):
                # If already running, that's fine, we'll monitor it
                if "already in progress" not in result.get('message', ''):
                    raise Exception(f"Failed to start trip detection: {result.get('message')}")
            
            self.detection_started = True
            
            # Monitor progress
            while not self.is_stopped():
                progress = self.trip_service.get_detection_progress()
                
                # Update our progress
                self.update_progress(
                    processed=progress.get('processed_emails', 0),
                    total=progress.get('total_emails', 0),
                    trips_found=progress.get('trips_found', 0),
                    status='processing' if progress.get('is_running') else 'completed'
                )
                
                # Check if finished
                if progress.get('finished', False):
                    logger.info("Trip Detection Stage: Detection finished")
                    
                    if progress.get('error'):
                        self.fail(progress.get('error'))
                    else:
                        self.complete()
                    break
                
                # Wait before checking again
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Trip detection stage failed: {e}")
            self.fail(str(e))
            raise
    
    def stop(self):
        """Stop trip detection stage"""
        super().stop()
        self.trip_service.stop_detection()
