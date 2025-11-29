"""
Gemini Provider - Direct implementation using Google Generative AI
"""
import logging
import os
import json
from typing import Dict
from backend.lib.ai.ai_provider_interface import AIProviderInterface

logger = logging.getLogger(__name__)


class GeminiProvider(AIProviderInterface):
    """Gemini implementation of AI Provider Interface"""
    
    def __init__(self, model_version: str = 'gemini-2.5-flash'):
        self.model_version = model_version
        self.model = None
        self.config = self._load_config()
        
        try:
            import google.generativeai as genai
            
            # Get API key from config or environment
            api_key = self.config.get('api_key') or os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("Gemini API key not found in config or environment")
            
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_version)
            logger.info(f"Initialized Gemini provider: {model_version}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini provider: {e}")
            raise
    
    def _load_config(self) -> Dict:
        """Load Gemini configuration from config file"""
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
            # Get timeout from config, default to 60 seconds
            timeout = self.config.get('timeout', 60)
            
            # Use request_options to set timeout
            from google.api_core import retry
            response = self.model.generate_content(
                prompt,
                request_options={'timeout': timeout}
            )
            
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
            
            # Calculate cost (disabled)
            cost_info = self.estimate_cost(input_tokens, output_tokens)
            
            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": 0.0
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
        """Calculate Gemini API cost (disabled)"""
        return {
            "estimated_cost_usd": 0.0,
            "input_cost_usd": 0.0,
            "output_cost_usd": 0.0,
            "model_pricing": {
                'input': 0.0,
                'output': 0.0,
                'long_context': False
            }
        }
    
    def count_tokens(self, text: str) -> int:
        """Count tokens for Gemini (optional implementation)"""
        try:
            # Try to use Gemini's count_tokens method if available
            if hasattr(self.model, 'count_tokens'):
                result = self.model.count_tokens(text)
                return result.total_tokens
        except Exception as e:
            logger.warning(f"Error counting tokens with Gemini API: {e}")
        
        # Fallback to character-based estimation
        return len(text) // 4