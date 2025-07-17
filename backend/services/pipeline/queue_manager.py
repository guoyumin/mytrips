"""
Queue Manager for Pipeline Processing
"""
import queue
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class PipelineQueueManager:
    """Manages queues for pipeline communication between stages"""
    
    def __init__(self, max_size: int = 10):
        self.queues = {
            'import_to_classification': queue.Queue(maxsize=max_size),
            'classification_to_content': queue.Queue(maxsize=max_size),
            'content_to_booking': queue.Queue(maxsize=max_size)
        }
    
    def put(self, queue_name: str, data: Optional[Dict], timeout: Optional[float] = None):
        """Put data into a queue"""
        if queue_name not in self.queues:
            raise ValueError(f"Unknown queue: {queue_name}")
        
        try:
            if timeout:
                self.queues[queue_name].put(data, timeout=timeout)
            else:
                self.queues[queue_name].put(data)
            
            if data is None:
                logger.debug(f"Sent end signal to {queue_name}")
            else:
                logger.debug(f"Put data into {queue_name}: {len(data.get('email_ids', []))} items")
        except queue.Full:
            logger.error(f"Queue {queue_name} is full")
            raise
    
    def get(self, queue_name: str, timeout: float = 1.0) -> Optional[Dict]:
        """Get data from a queue with timeout"""
        if queue_name not in self.queues:
            raise ValueError(f"Unknown queue: {queue_name}")
        
        try:
            return self.queues[queue_name].get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_queue(self, queue_name: str) -> queue.Queue:
        """Get a queue object directly"""
        if queue_name not in self.queues:
            raise ValueError(f"Unknown queue: {queue_name}")
        return self.queues[queue_name]
    
    def clear_all(self):
        """Clear all queues"""
        for name in self.queues:
            self.clear_queue(name)
    
    def clear_queue(self, queue_name: str):
        """Clear a specific queue"""
        if queue_name not in self.queues:
            raise ValueError(f"Unknown queue: {queue_name}")
        
        q = self.queues[queue_name]
        cleared = 0
        while not q.empty():
            try:
                q.get_nowait()
                cleared += 1
            except queue.Empty:
                break
        
        if cleared > 0:
            logger.debug(f"Cleared {cleared} items from {queue_name}")
    
    def send_end_signals(self):
        """Send end signals to all queues"""
        for queue_name in self.queues:
            self.put(queue_name, None)
    
    def is_empty(self, queue_name: str) -> bool:
        """Check if a queue is empty"""
        if queue_name not in self.queues:
            raise ValueError(f"Unknown queue: {queue_name}")
        return self.queues[queue_name].empty()
    
    def qsize(self, queue_name: str) -> int:
        """Get approximate size of a queue"""
        if queue_name not in self.queues:
            raise ValueError(f"Unknown queue: {queue_name}")
        return self.queues[queue_name].qsize()