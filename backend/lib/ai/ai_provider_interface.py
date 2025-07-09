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
    def generate_content(self, prompt: str) -> Dict:
        """
        Send prompt to AI model and return response with token usage
        
        Args:
            prompt: The text prompt to send to the AI model
            
        Returns:
            Dict containing:
                - content: str - The AI response text
                - input_tokens: int - Number of input tokens
                - output_tokens: int - Number of output tokens
                - total_tokens: int - Total tokens used
                - estimated_cost_usd: float - Estimated cost in USD
            
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
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Dict:
        """
        Calculate the cost based on token counts
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Dict containing cost calculation details
        """
        pass
    
    def count_tokens(self, text: str) -> int:
        """
        Optional: Count tokens in the given text without making API call
        
        Args:
            text: The text to count tokens for
            
        Returns:
            Number of tokens
            
        Raises:
            NotImplementedError: If not implemented by the provider
        """
        raise NotImplementedError(f"Token counting not implemented for {self.__class__.__name__}")
    
    def generate_content_simple(self, prompt: str) -> str:
        """
        Legacy method that returns only content string for backward compatibility
        
        Args:
            prompt: The text prompt to send to the AI model
            
        Returns:
            Response text from the AI model
        """
        response = self.generate_content(prompt)
        return response['content']