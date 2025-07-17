"""
State Manager for Pipeline Processing
"""
import threading
from datetime import datetime
from typing import Dict, Optional, Any

import logging

logger = logging.getLogger(__name__)


class PipelineStateManager:
    """Manages the state of the entire pipeline with thread-safe operations"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.state = self._create_initial_state()
    
    def _create_initial_state(self) -> Dict[str, Any]:
        """Create the initial pipeline state structure"""
        return {
            'is_running': False,
            'current_stage': None,
            'date_range': None,
            'start_time': None,
            'end_time': None,
            'stages': {
                'import': self._create_stage_state(),
                'classification': self._create_stage_state(),
                'content': self._create_stage_state(),
                'booking': self._create_stage_state()
            },
            'errors': [],
            'message': ''
        }
    
    def _create_stage_state(self) -> Dict[str, Any]:
        """Create initial state for a stage"""
        return {
            'status': 'pending',  # pending, in_progress, completed, failed
            'progress': 0,
            'total': 0,
            'processed': 0,
            'failed': 0,
            'start_time': None,
            'end_time': None
        }
    
    def reset(self):
        """Reset the entire pipeline state"""
        with self._lock:
            self.state = self._create_initial_state()
    
    def start_pipeline(self, date_range: Dict):
        """Mark pipeline as started"""
        with self._lock:
            self.state['is_running'] = True
            self.state['date_range'] = date_range
            self.state['start_time'] = datetime.now()
            self.state['message'] = 'Pipeline started'
            logger.info(f"Pipeline started for date range: {date_range}")
    
    def stop_pipeline(self, message: str = 'Pipeline stopped'):
        """Mark pipeline as stopped"""
        with self._lock:
            self.state['is_running'] = False
            self.state['end_time'] = datetime.now()
            self.state['current_stage'] = None
            self.state['message'] = message
            logger.info(message)
    
    def set_current_stage(self, stage_name: str):
        """Set the current active stage"""
        with self._lock:
            self.state['current_stage'] = stage_name
    
    def update_stage(self, stage_name: str, updates: Dict[str, Any]):
        """Update a specific stage's state"""
        with self._lock:
            if stage_name in self.state['stages']:
                self.state['stages'][stage_name].update(updates)
    
    def get_stage_progress(self, stage_name: str) -> Dict[str, Any]:
        """Get progress for a specific stage"""
        with self._lock:
            if stage_name in self.state['stages']:
                return self.state['stages'][stage_name].copy()
            return {}
    
    def add_error(self, stage: str, error: str):
        """Add an error to the pipeline state"""
        with self._lock:
            self.state['errors'].append({
                'stage': stage,
                'error': error,
                'timestamp': datetime.now().isoformat()
            })
            logger.error(f"Pipeline error in {stage}: {error}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get a copy of the entire pipeline state"""
        with self._lock:
            return self.state.copy()
    
    def get_progress(self) -> Dict[str, Any]:
        """Get pipeline progress with calculated overall progress"""
        with self._lock:
            progress = self.state.copy()
            
            # Calculate overall progress
            stage_weights = {
                'import': 25,
                'classification': 25,
                'content': 25,
                'booking': 25
            }
            
            overall_progress = 0
            for stage, weight in stage_weights.items():
                stage_progress = self.state['stages'][stage]['progress']
                overall_progress += (stage_progress * weight) / 100
            
            progress['overall_progress'] = int(overall_progress)
            
            # Add elapsed time
            if self.state['start_time']:
                if self.state['end_time']:
                    elapsed = (self.state['end_time'] - self.state['start_time']).total_seconds()
                else:
                    elapsed = (datetime.now() - self.state['start_time']).total_seconds()
                progress['elapsed_time'] = int(elapsed)
            
            return progress
    
    def is_running(self) -> bool:
        """Check if pipeline is running"""
        with self._lock:
            return self.state['is_running']
    
    def update_stage_from_progress(self, stage_name: str, progress: Dict[str, Any]):
        """Update stage state from stage progress dict"""
        with self._lock:
            if stage_name in self.state['stages']:
                # Map progress fields to stage state
                stage_state = self.state['stages'][stage_name]
                
                # Update standard fields
                for field in ['status', 'progress', 'total', 'processed', 'failed', 'start_time', 'end_time']:
                    if field in progress:
                        stage_state[field] = progress[field]
                
                # Update stage-specific fields
                if stage_name == 'classification' and 'travel_count' in progress:
                    stage_state['travel_count'] = progress['travel_count']
                elif stage_name == 'booking' and 'bookings_found' in progress:
                    stage_state['bookings_found'] = progress['bookings_found']