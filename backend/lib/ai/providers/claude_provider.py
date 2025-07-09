"""
Claude Provider - Provides Anthropic Claude models
"""
import json
import os
import logging
from typing import Dict
from lib.ai.ai_provider_interface import AIProviderInterface

logger = logging.getLogger(__name__)


class ClaudeProvider(AIProviderInterface):
    """Claude implementation of AI Provider Interface"""
    
    def __init__(self, model_version: str = None):
        # Load config first to get default model if not specified
        config = self._load_config()
        self.model_version = model_version or config.get('model', 'claude-3-opus-20240229')
        self.client = None
        
        try:
            # Try to import and initialize Anthropic
            from anthropic import Anthropic
            
            api_key = config.get('api_key')
            if not api_key or api_key == 'YOUR_CLAUDE_API_KEY_HERE':
                raise ValueError("Claude API key not configured. Please update config/claude_config.json")
            
            self.client = Anthropic(api_key=api_key)
            logger.info(f"Initialized Claude provider: {self.model_version}")
        except ImportError:
            logger.error("Anthropic library not installed. Install with: pip install anthropic")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Claude provider: {e}")
            raise
    
    def generate_content(self, prompt: str) -> str:
        """Generate content using Claude"""
        try:
            message = self.client.messages.create(
                model=self.model_version,
                max_tokens=4096,
                temperature=0.1,
                system="You are a helpful assistant for travel booking analysis.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            # Claude returns content in a different format
            return message.content[0].text if message.content else ""
        except Exception as e:
            logger.error(f"Claude generate_content error: {e}")
            raise Exception(f"Claude API error: {str(e)}")
    
    def _load_config(self) -> Dict:
        """Load Claude configuration from config file"""
        # Get project root (4 levels up from backend/lib/ai/providers/)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        config_path = os.path.join(project_root, 'config', 'claude_config.json')
        
        if not os.path.exists(config_path):
            raise Exception(f"Claude config not found. Please create {config_path} with your API key")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        return config
    
    def get_model_info(self) -> Dict:
        """Get information about the Claude model"""
        model_names = {
            "claude-3-opus-20240229": "Claude 3 Opus",
            "claude-3-sonnet-20240229": "Claude 3 Sonnet",
            "claude-3-haiku-20240307": "Claude 3 Haiku"
        }
        
        return {
            "provider": "Anthropic",
            "model_name": model_names.get(self.model_version, f"Claude {self.model_version}"),
            "version": self.model_version,
            "type": "Large Language Model"
        }
    
    def estimate_cost(self, prompt_length: int) -> Dict:
        """Estimate Claude API cost"""
        chars_per_token = 4
        input_tokens = prompt_length // chars_per_token
        output_tokens = 2000  # Estimated output
        
        # Claude pricing (approximate, varies by model)
        pricing_per_1m = {
            "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},  # Most expensive
            "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},  # Medium
            "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25}   # Cheapest
        }
        
        model_pricing = pricing_per_1m.get(self.model_version, pricing_per_1m["claude-3-sonnet-20240229"])
        
        input_cost = (input_tokens / 1_000_000) * model_pricing["input"]
        output_cost = (output_tokens / 1_000_000) * model_pricing["output"]
        cost = input_cost + output_cost
        
        return {
            "estimated_cost_usd": cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost_per_1m": model_pricing["input"],
            "output_cost_per_1m": model_pricing["output"]
        }