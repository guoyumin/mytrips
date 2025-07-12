"""
DeepSeek Provider - Local DeepSeek R1 models via Ollama
"""
import json
import os
import logging
import requests
from typing import Dict, Optional
from backend.lib.ai.ai_provider_interface import AIProviderInterface

logger = logging.getLogger(__name__)


class DeepSeekProvider(AIProviderInterface):
    """DeepSeek implementation of AI Provider Interface for local models via Ollama"""
    
    def __init__(self, model_version: str = None):
        # Load config first to get default model if not specified
        self.config = self._load_config()
        self.base_url = self.config.get('base_url', 'http://localhost:11434')
        self.model_version = model_version or self.config.get('model', 'deepseek-r1:14b')
        
        # Test connection to Ollama server
        try:
            self._test_connection()
            logger.info(f"Initialized DeepSeek provider: {self.model_version} at {self.base_url}")
        except Exception as e:
            logger.error(f"Failed to initialize DeepSeek provider: {e}")
            raise
    
    def _test_connection(self):
        """Test connection to Ollama server"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                raise Exception(f"Ollama server returned status {response.status_code}")
            
            # Check if our model is available
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            if self.model_version not in model_names:
                logger.warning(f"Model {self.model_version} not found in Ollama server. Available models: {model_names}")
                # Don't fail - model might be pulled on first use
        except requests.exceptions.RequestException as e:
            raise Exception(f"Cannot connect to Ollama server at {self.base_url}: {str(e)}")
    
    def generate_content(self, prompt: str) -> Dict:
        """Generate content using Ollama and return response with token usage"""
        try:
            # Prepare request to Ollama chat API
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model_version,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant for travel booking analysis. Provide structured, accurate responses."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            }
            
            # Make request with longer timeout for local models
            response = requests.post(url, json=payload, timeout=300)
            
            if response.status_code != 200:
                error_msg = f"Ollama API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Parse response
            result = response.json()
            
            # Extract content and token usage
            content = result.get('message', {}).get('content', '')
            
            # Ollama provides token counts in eval_count and prompt_eval_count
            prompt_tokens = result.get('prompt_eval_count', 0)
            output_tokens = result.get('eval_count', 0)
            
            # If token counts not provided, estimate them
            if prompt_tokens == 0:
                prompt_tokens = self._estimate_tokens(prompt)
            if output_tokens == 0:
                output_tokens = self._estimate_tokens(content)
            
            total_tokens = prompt_tokens + output_tokens
            
            # Local models have zero cost
            return {
                "content": content,
                "input_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": 0.0  # Always zero for local models
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"Ollama request timed out after 300 seconds")
            raise Exception("Ollama API timeout - model may be too slow or not loaded")
        except Exception as e:
            logger.error(f"Ollama generate_content error: {e}")
            raise Exception(f"Ollama API error: {str(e)}")
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count based on string length"""
        # Rough estimation: ~4 characters per token for English text
        # This is a simplified heuristic
        return max(1, len(text) // 4)
    
    def _load_config(self) -> Dict:
        """Load Ollama configuration from config file"""
        # Get project root (4 levels up from backend/lib/ai/providers/)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        config_path = os.path.join(project_root, 'config', 'deepseek_config.json')
        
        # Default config if file doesn't exist
        default_config = {
            "base_url": "http://localhost:11434",
            "model": "deepseek-r1:14b",
            "model_mapping": {
                "fast": "deepseek-r1:7b",
                "powerful": "deepseek-r1:14b"
            }
        }
        
        if not os.path.exists(config_path):
            logger.warning(f"DeepSeek config not found at {config_path}, using defaults")
            return default_config
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Error loading DeepSeek config: {e}, using defaults")
            return default_config
    
    def get_model_info(self) -> Dict:
        """Get information about the DeepSeek model"""
        model_size = "7B" if "7b" in self.model_version.lower() else "14B" if "14b" in self.model_version.lower() else "Unknown"
        return {
            "provider": "DeepSeek (Local via Ollama)",
            "model_name": f"DeepSeek R1 {model_size}",
            "version": self.model_version,
            "type": "Local Large Language Model",
            "base_url": self.base_url
        }
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Dict:
        """Calculate cost - always zero for local models"""
        return {
            "estimated_cost_usd": 0.0,
            "input_cost_usd": 0.0,
            "output_cost_usd": 0.0,
            "model": self.model_version,
            "note": "Local model - no API costs"
        }
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in the given text using estimation"""
        return self._estimate_tokens(text)