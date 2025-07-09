"""
Gemini Provider - Wraps existing GeminiService
"""
import logging
from typing import Dict
from lib.ai.ai_provider_interface import AIProviderInterface
from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class GeminiProvider(AIProviderInterface):
    """Gemini implementation of AI Provider Interface"""
    
    def __init__(self, model_version: str = 'gemini-2.5-flash'):
        self.model_version = model_version
        self.gemini_service = None
        
        try:
            self.gemini_service = GeminiService(model_version)
            logger.info(f"Initialized Gemini provider: {model_version}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini provider: {e}")
            raise
    
    def generate_content(self, prompt: str) -> str:
        """Generate content using Gemini"""
        try:
            response = self.gemini_service.model.generate_content(prompt)
            return response.text if hasattr(response, 'text') else str(response)
        except Exception as e:
            logger.error(f"Gemini generate_content error: {e}")
            # Re-raise with more context
            raise Exception(f"Gemini API error: {str(e)}")
    
    def get_model_info(self) -> Dict:
        """Get information about the Gemini model"""
        return {
            "provider": "Google",
            "model_name": f"Gemini {self.model_version}",
            "version": self.model_version,
            "type": "Large Language Model"
        }
    
    def estimate_cost(self, prompt_length: int) -> Dict:
        """Estimate Gemini API cost"""
        if self.gemini_service:
            # Use existing cost estimation method
            # Convert characters to rough email count for existing method
            email_count = max(1, prompt_length // 1000)  # Rough estimation
            return self.gemini_service.estimate_token_cost(email_count, 'general')
        
        # Fallback estimation
        chars_per_token = 4
        input_tokens = prompt_length // chars_per_token
        output_tokens = 1000  # Estimated output
        
        # Gemini 2.5 Flash pricing (rough estimate)
        input_cost_per_1m = 0.075  # $0.075 per 1M input tokens
        output_cost_per_1m = 0.3   # $0.3 per 1M output tokens
        
        cost = (input_tokens / 1_000_000 * input_cost_per_1m) + (output_tokens / 1_000_000 * output_cost_per_1m)
        
        return {
            "estimated_cost_usd": cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }