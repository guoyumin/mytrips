"""
OpenAI Provider - Provides OpenAI GPT models
"""
import json
import os
import logging
from typing import Dict
from backend.lib.ai.ai_provider_interface import AIProviderInterface

logger = logging.getLogger(__name__)

# Try to import tiktoken for token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not available for local token counting")


class OpenAIProvider(AIProviderInterface):
    """OpenAI implementation of AI Provider Interface"""
    
    def __init__(self, model_version: str = None):
        # Load config first to get default model if not specified
        self.config = self._load_config()
        self.model_version = model_version or self.config.get('model', 'gpt-4-turbo-preview')
        self.client = None
        
        try:
            # Try to import and initialize OpenAI
            from openai import OpenAI
            
            api_key = self.config.get('api_key')
            if not api_key or api_key == 'YOUR_OPENAI_API_KEY_HERE':
                raise ValueError("OpenAI API key not configured. Please update config/openai_config.json")
            
            self.client = OpenAI(api_key=api_key)
            logger.info(f"Initialized OpenAI provider: {self.model_version}")
        except ImportError:
            logger.error("OpenAI library not installed. Install with: pip install openai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI provider: {e}")
            raise
    
    def generate_content(self, prompt: str) -> Dict:
        """Generate content using OpenAI GPT and return response with token usage"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_version,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for travel booking analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
                # Don't limit max_tokens - let the model use what it needs
            )
            
            # Extract content and usage info
            content = response.choices[0].message.content
            usage = response.usage
            
            # Calculate cost
            cost_info = self.estimate_cost(usage.prompt_tokens, usage.completion_tokens)
            
            return {
                "content": content,
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "estimated_cost_usd": cost_info["estimated_cost_usd"]
            }
        except Exception as e:
            logger.error(f"OpenAI generate_content error: {e}")
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def _load_config(self) -> Dict:
        """Load OpenAI configuration from config file"""
        # Get project root (4 levels up from backend/lib/ai/providers/)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        config_path = os.path.join(project_root, 'config', 'openai_config.json')
        
        if not os.path.exists(config_path):
            raise Exception(f"OpenAI config not found. Please create {config_path} with your API key")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        return config
    
    def get_model_info(self) -> Dict:
        """Get information about the OpenAI model"""
        return {
            "provider": "OpenAI",
            "model_name": f"GPT {self.model_version}",
            "version": self.model_version,
            "type": "Large Language Model"
        }
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Dict:
        """Calculate OpenAI API cost based on token counts"""
        # Get pricing from config
        pricing_config = self.config.get('pricing', {})
        
        # Find matching pricing for the model
        model_pricing = None
        # First try exact match
        if self.model_version in pricing_config:
            price_info = pricing_config[self.model_version]
            model_pricing = {
                'input': price_info['input_per_1m'] / 1000,  # Convert to per 1K tokens
                'output': price_info['output_per_1m'] / 1000
            }
        else:
            # Then try partial match (but check for longer matches first)
            model_lower = self.model_version.lower()
            best_match = None
            best_match_len = 0
            
            for model_key in pricing_config.keys():
                if model_key.lower() in model_lower and len(model_key) > best_match_len:
                    best_match = model_key
                    best_match_len = len(model_key)
            
            if best_match:
                price_info = pricing_config[best_match]
                model_pricing = {
                    'input': price_info['input_per_1m'] / 1000,
                    'output': price_info['output_per_1m'] / 1000
                }
                logger.info(f"Using pricing for {best_match} for model {self.model_version}")
        
        # Default to GPT-4 pricing if model not found
        if not model_pricing:
            logger.warning(f"Unknown model {self.model_version}, using GPT-4 pricing")
            gpt4_pricing = pricing_config.get('gpt-4', {'input_per_1m': 30.0, 'output_per_1m': 60.0})
            model_pricing = {
                'input': gpt4_pricing['input_per_1m'] / 1000,
                'output': gpt4_pricing['output_per_1m'] / 1000
            }
        
        # Calculate cost
        input_cost = (input_tokens / 1000) * model_pricing['input']
        output_cost = (output_tokens / 1000) * model_pricing['output']
        total_cost = input_cost + output_cost
        
        return {
            "estimated_cost_usd": total_cost,
            "input_cost_usd": input_cost,
            "output_cost_usd": output_cost,
            "model_pricing": model_pricing
        }
    
    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken library"""
        if not TIKTOKEN_AVAILABLE:
            # Fallback to character-based estimation
            return len(text) // 4
        
        try:
            # Get the appropriate encoding for the model
            if 'gpt-4o' in self.model_version:
                encoding = tiktoken.get_encoding("o200k_base")
            else:
                encoding = tiktoken.encoding_for_model(self.model_version)
            
            tokens = encoding.encode(text)
            return len(tokens)
        except Exception as e:
            logger.warning(f"Error counting tokens with tiktoken: {e}, falling back to estimation")
            return len(text) // 4