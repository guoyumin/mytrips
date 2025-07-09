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
        self.config = self._load_config()
        
        try:
            self.gemini_service = GeminiService(model_version)
            logger.info(f"Initialized Gemini provider: {model_version}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini provider: {e}")
            raise
    
    def _load_config(self) -> Dict:
        """Load Gemini configuration from config file"""
        import os
        import json
        # Get project root (4 levels up from backend/lib/ai/providers/)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        config_path = os.path.join(project_root, 'config', 'gemini_config.json')
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def generate_content(self, prompt: str) -> Dict:
        """Generate content using Gemini and return response with token usage"""
        try:
            response = self.gemini_service.model.generate_content(prompt)
            
            # Extract content
            content = response.text if hasattr(response, 'text') else str(response)
            
            # Extract token usage from response metadata
            input_tokens = 0
            output_tokens = 0
            
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                input_tokens = getattr(usage, 'prompt_token_count', 0)
                output_tokens = getattr(usage, 'candidates_token_count', 0)
                total_tokens = getattr(usage, 'total_token_count', input_tokens + output_tokens)
            else:
                # Fallback estimation if usage metadata not available
                logger.warning("Gemini response missing usage_metadata, estimating tokens")
                input_tokens = len(prompt) // 4
                output_tokens = len(content) // 4
                total_tokens = input_tokens + output_tokens
            
            # Calculate cost
            cost_info = self.estimate_cost(input_tokens, output_tokens)
            
            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": cost_info["estimated_cost_usd"]
            }
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
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Dict:
        """Calculate Gemini API cost based on token counts"""
        # Get pricing from config
        pricing_config = self.config.get('pricing', {})
        
        # Find matching pricing for the model
        model_pricing_info = None
        for model_key, price_info in pricing_config.items():
            if model_key in self.model_version.lower():
                model_pricing_info = price_info
                break
        
        # Default to Gemini 1.5 Flash pricing if model not found
        if not model_pricing_info:
            logger.warning(f"Unknown model {self.model_version}, using Gemini 1.5 Flash pricing")
            model_pricing_info = pricing_config.get('gemini-1.5-flash', {
                'input_per_1m': 0.075, 'output_per_1m': 0.30
            })
        
        # Check if we need to use long context pricing
        use_long_context = False
        if 'long_context_threshold' in model_pricing_info and input_tokens > model_pricing_info['long_context_threshold']:
            use_long_context = True
            logger.info(f"Using long context pricing for {input_tokens} tokens")
        
        # Get appropriate pricing
        if use_long_context and 'input_per_1m_long' in model_pricing_info:
            input_price = model_pricing_info['input_per_1m_long']
            output_price = model_pricing_info['output_per_1m_long']
        else:
            input_price = model_pricing_info['input_per_1m']
            output_price = model_pricing_info['output_per_1m']
        
        # Calculate cost (pricing is per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price
        total_cost = input_cost + output_cost
        
        return {
            "estimated_cost_usd": total_cost,
            "input_cost_usd": input_cost,
            "output_cost_usd": output_cost,
            "model_pricing": {
                'input': input_price,
                'output': output_price,
                'long_context': use_long_context
            }
        }
    
    def count_tokens(self, text: str) -> int:
        """Count tokens for Gemini (optional implementation)"""
        try:
            # Try to use Gemini's count_tokens method if available
            if hasattr(self.gemini_service.model, 'count_tokens'):
                result = self.gemini_service.model.count_tokens(text)
                return result.total_tokens
        except Exception as e:
            logger.warning(f"Error counting tokens with Gemini API: {e}")
        
        # Fallback to character-based estimation
        return len(text) // 4