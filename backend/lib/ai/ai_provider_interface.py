"""
AI Provider Interface - Low-level abstraction for AI model calls
"""
from abc import ABC, abstractmethod
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class AIProviderInterface(ABC):
    """Low-level interface for AI providers - only handles model interaction"""
    
    @abstractmethod
    def generate_content(self, prompt: str) -> str:
        """
        Send prompt to AI model and return response text
        
        Args:
            prompt: The text prompt to send to the AI model
            
        Returns:
            Response text from the AI model
            
        Raises:
            Exception: If the AI call fails
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict:
        """
        Get information about the current model
        
        Returns:
            Dict containing model name, version, provider, etc.
        """
        pass
    
    @abstractmethod
    def estimate_cost(self, prompt_length: int) -> Dict:
        """
        Estimate the cost of an API call
        
        Args:
            prompt_length: Length of the prompt in characters
            
        Returns:
            Dict containing cost estimation details
        """
        pass