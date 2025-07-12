"""
Claude Provider - Provides Anthropic Claude models
"""
import json
import os
import logging
from typing import Dict
from backend.lib.ai.ai_provider_interface import AIProviderInterface

logger = logging.getLogger(__name__)


class ClaudeProvider(AIProviderInterface):
    """Claude implementation of AI Provider Interface"""
    
    def __init__(self, model_version: str = None):
        # Load config first to get default model if not specified
        self.config = self._load_config()
        self.model_version = model_version or self.config.get('model', 'claude-3-opus-20240229')
        self.client = None
        
        try:
            # Try to import and initialize Anthropic
            from anthropic import Anthropic
            
            api_key = self.config.get('api_key')
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
    
    def generate_content(self, prompt: str) -> Dict:
        """Generate content using Claude and return response with token usage"""
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
            
            # Extract content
            content = message.content[0].text if message.content else ""
            
            # Extract token usage
            usage = message.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
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
            "claude-3-haiku-20240307": "Claude 3 Haiku",
            "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
            "claude-3-5-haiku-20241022": "Claude 3.5 Haiku",
            "claude-opus-4-20250514": "Claude Opus 4"
        }
        
        return {
            "provider": "Anthropic",
            "model_name": model_names.get(self.model_version, f"Claude {self.model_version}"),
            "version": self.model_version,
            "type": "Large Language Model"
        }
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Dict:
        """Calculate Claude API cost based on token counts"""
        # Get pricing from config
        pricing_config = self.config.get('pricing', {})
        
        # Find matching pricing for the model
        model_pricing_info = pricing_config.get(self.model_version)
        
        # Default to Claude 3 Sonnet pricing if model not found
        if not model_pricing_info:
            logger.warning(f"Unknown model {self.model_version}, using Claude 3 Sonnet pricing")
            model_pricing_info = pricing_config.get("claude-3-sonnet-20240229", {
                "input_per_1m": 3.0, "output_per_1m": 15.0
            })
        
        # Calculate cost (pricing is per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * model_pricing_info.get("input_per_1m", 3.0)
        output_cost = (output_tokens / 1_000_000) * model_pricing_info.get("output_per_1m", 15.0)
        total_cost = input_cost + output_cost
        
        return {
            "estimated_cost_usd": total_cost,
            "input_cost_usd": input_cost,
            "output_cost_usd": output_cost,
            "model_pricing": {
                "input": model_pricing_info.get("input_per_1m", 3.0),
                "output": model_pricing_info.get("output_per_1m", 15.0)
            }
        }
    
    def count_tokens(self, text: str) -> int:
        """Count tokens using Claude's API (optional implementation)"""
        try:
            # Use Claude's count_tokens endpoint if needed
            response = self.client.messages.count_tokens(
                model=self.model_version,
                messages=[{"role": "user", "content": text}]
            )
            return response.input_tokens
        except Exception as e:
            logger.warning(f"Error counting tokens with Claude API: {e}")
            # Fallback to character-based estimation
            return len(text) // 4