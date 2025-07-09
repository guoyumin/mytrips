"""
OpenAI Provider - Provides OpenAI GPT models
"""
import json
import os
import logging
from typing import Dict
from lib.ai.ai_provider_interface import AIProviderInterface

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProviderInterface):
    """OpenAI implementation of AI Provider Interface"""
    
    def __init__(self, model_version: str = None):
        # Load config first to get default model if not specified
        config = self._load_config()
        self.model_version = model_version or config.get('model', 'gpt-4-turbo-preview')
        self.client = None
        
        try:
            # Try to import and initialize OpenAI
            from openai import OpenAI
            
            api_key = config.get('api_key')
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
    
    def generate_content(self, prompt: str) -> str:
        """Generate content using OpenAI GPT"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_version,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for travel booking analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4096
            )
            return response.choices[0].message.content
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
    
    def estimate_cost(self, prompt_length: int) -> Dict:
        """Estimate OpenAI API cost"""
        chars_per_token = 4
        input_tokens = prompt_length // chars_per_token
        output_tokens = 2000  # Estimated output
        
        # OpenAI pricing (rough estimates, varies by model)
        if 'gpt-4' in self.model_version.lower():
            input_cost_per_1k = 0.01
            output_cost_per_1k = 0.03
        else:  # GPT-3.5
            input_cost_per_1k = 0.001
            output_cost_per_1k = 0.002
        
        cost = (input_tokens / 1000 * input_cost_per_1k) + (output_tokens / 1000 * output_cost_per_1k)
        
        return {
            "estimated_cost_usd": cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }