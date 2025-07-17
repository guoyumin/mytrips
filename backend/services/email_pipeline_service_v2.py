"""
Email Pipeline Service V2 - Refactored with modular architecture
"""
import logging
import threading
import concurrent.futures
from typing import Dict, Optional

from backend.services.pipeline.queue_manager import PipelineQueueManager
from backend.services.pipeline.state_manager import PipelineStateManager
from backend.services.pipeline.stages.import_stage import ImportStage
from backend.services.pipeline.stages.classification_stage import ClassificationStage
from backend.services.pipeline.stages.content_stage import ContentExtractionStage
from backend.services.pipeline.stages.booking_stage import BookingExtractionStage

logger = logging.getLogger(__name__)


class EmailPipelineServiceV2:
    """Refactored email pipeline service with modular architecture"""
    
    def __init__(self):
        """Initialize pipeline components"""
        try:
            # Initialize core components
            self.queue_manager = PipelineQueueManager(max_size=10)
            self.state_manager = PipelineStateManager()
            
            # Initialize pipeline stages
            self.import_stage = ImportStage(batch_size=100)
            self.classification_stage = ClassificationStage(batch_size=20)
            self.content_stage = ContentExtractionStage(batch_size=10)
            self.booking_stage = BookingExtractionStage(batch_size=10)
            
            # Threading control
            self._stop_flag = threading.Event()
            self._pipeline_thread = None
            self._lock = threading.Lock()
            
            logger.info("Email pipeline service V2 initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize email pipeline service V2: {e}")
            raise
    
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
            if self.state_manager.is_running():
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
            
            # Reset state and queues
            self.state_manager.reset()
            self.queue_manager.clear_all()
            self._stop_flag.clear()
            
            # Start pipeline
            self.state_manager.start_pipeline(date_range)
            
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
        logger.info("stop_pipeline called")
        with self._lock:
            is_running = self.state_manager.is_running()
            logger.info(f"Pipeline is_running: {is_running}")
            
            if not is_running:
                return {
                    'stopped': False,
                    'message': 'Pipeline is not running'
                }
            
            # Set stop flag
            self._stop_flag.set()
            logger.info("Stop flag set")
            
            # Stop all stages
            logger.info("Stopping all stages...")
            self.import_stage.stop()
            self.classification_stage.stop()
            self.content_stage.stop()
            self.booking_stage.stop()
            
            # Update state
            self.state_manager.stop_pipeline('Pipeline stop requested')
            
            logger.info("Pipeline stop requested - completed")
            
            return {
                'stopped': True,
                'message': 'Pipeline stop requested. Current operations will complete before stopping.'
            }
    
    def get_pipeline_progress(self) -> Dict:
        """Get current pipeline progress"""
        # Get overall state
        progress = self.state_manager.get_progress()
        
        # Update with latest stage progress
        for stage_name, stage in [
            ('import', self.import_stage),
            ('classification', self.classification_stage),
            ('content', self.content_stage),
            ('booking', self.booking_stage)
        ]:
            stage_progress = stage.get_progress()
            self.state_manager.update_stage_from_progress(stage_name, stage_progress)
        
        return self.state_manager.get_progress()
    
    def _run_pipeline(self, date_range: Dict):
        """
        Main pipeline execution logic
        
        Args:
            date_range: Dictionary with date range for import
        """
        try:
            logger.info("Starting pipeline execution")
            
            # Get queues
            import_to_classification = self.queue_manager.get_queue('import_to_classification')
            classification_to_content = self.queue_manager.get_queue('classification_to_content')
            content_to_booking = self.queue_manager.get_queue('content_to_booking')
            
            # Use ThreadPoolExecutor for parallel execution
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                # Start all pipeline stages
                futures = []
                
                # Stage 1: Import emails
                self.state_manager.set_current_stage('import')
                import_future = executor.submit(
                    self.import_stage.run_import,
                    date_range,
                    import_to_classification
                )
                futures.append(import_future)
                
                # Stage 2: Classification
                self.state_manager.set_current_stage('classification')
                classification_future = executor.submit(
                    self.classification_stage.run_classification,
                    import_to_classification,
                    classification_to_content
                )
                futures.append(classification_future)
                
                # Stage 3: Content extraction
                self.state_manager.set_current_stage('content')
                content_future = executor.submit(
                    self.content_stage.run_extraction,
                    classification_to_content,
                    content_to_booking
                )
                futures.append(content_future)
                
                # Stage 4: Booking extraction
                self.state_manager.set_current_stage('booking')
                booking_future = executor.submit(
                    self.booking_stage.run_extraction,
                    content_to_booking
                )
                futures.append(booking_future)
                
                # Monitor stage progress
                monitor_future = executor.submit(self._monitor_stages)
                futures.append(monitor_future)
                
                # Wait for all stages to complete or stop
                concurrent.futures.wait(futures)
                
                # Check if all completed successfully
                success = all(not future.exception() for future in futures)
                
                if success and not self._stop_flag.is_set():
                    self.state_manager.stop_pipeline('Pipeline completed successfully')
                elif self._stop_flag.is_set():
                    self.state_manager.stop_pipeline('Pipeline stopped by user')
                else:
                    self.state_manager.stop_pipeline('Pipeline completed with errors')
                
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            self.state_manager.stop_pipeline(f'Pipeline failed: {str(e)}')
            self.state_manager.add_error('pipeline', str(e))
    
    def _monitor_stages(self):
        """Monitor and update stage progress in state manager"""
        logger.info("Monitor stages started")
        while not self._stop_flag.is_set() and self.state_manager.is_running():
            # Update state manager with stage progress
            for stage_name, stage in [
                ('import', self.import_stage),
                ('classification', self.classification_stage),
                ('content', self.content_stage),
                ('booking', self.booking_stage)
            ]:
                progress = stage.get_progress()
                self.state_manager.update_stage_from_progress(stage_name, progress)
            
            # Wait before next update
            threading.Event().wait(1)
        
        logger.info(f"Monitor stages stopped - stop_flag: {self._stop_flag.is_set()}, is_running: {self.state_manager.is_running()}")