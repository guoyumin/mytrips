"""
AI Provider with Fallback - Wrapper that provides automatic fallback between multiple AI providers
"""
import logging
from typing import List, Tuple, Dict, Optional
from backend.lib.ai.ai_provider_interface import AIProviderInterface
from backend.lib.ai.ai_provider_factory import AIProviderFactory

logger = logging.getLogger(__name__)


class AIProviderWithFallback(AIProviderInterface):
    """
    AI Provider wrapper that automatically falls back to alternative providers on failure
    
    This class wraps multiple AI providers and provides automatic fallback functionality.
    When the current provider fails, it automatically switches to the next provider in the list.
    """
    
    def __init__(self, provider_configs: List[Tuple[str, str]]):
        """
        Initialize with a list of provider configurations
        
        Args:
            provider_configs: List of (provider_name, model_tier) tuples in priority order
                             Example: [('openai', 'fast'), ('gemini', 'fast')]
        """
        if not provider_configs:
            raise ValueError("At least one provider configuration must be specified")
            
        self.provider_configs = provider_configs
        self._current_index = 0
        self._current_provider: Optional[AIProviderInterface] = None
        
        # Initialize the first provider
        self._initialize_provider()
    
    def _initialize_provider(self) -> bool:
        """
        Initialize the current provider based on _current_index
        
        Returns:
            True if successful, False if all providers exhausted
        """
        if self._current_index >= len(self.provider_configs):
            logger.error("All providers exhausted in fallback order")
            return False
        
        provider_name, model_tier = self.provider_configs[self._current_index]
        
        try:
            logger.info(f"Initializing provider: {provider_name}-{model_tier}")
            self._current_provider = AIProviderFactory.create_provider(
                model_tier=model_tier,
                provider_name=provider_name
            )
            
            model_info = self._current_provider.get_model_info()
            logger.info(f"Successfully initialized: {model_info['model_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize {provider_name}-{model_tier}: {e}")
            # Try next provider
            self._current_index += 1
            return self._initialize_provider()
    
    def _switch_to_next_provider(self) -> bool:
        """
        Switch to the next provider in the fallback order
        
        Returns:
            True if successful, False if all providers exhausted
        """
        self._current_index += 1
        
        if self._current_index >= len(self.provider_configs):
            logger.error("All providers exhausted in fallback order")
            return False
        
        provider_name, model_tier = self.provider_configs[self._current_index]
        
        try:
            logger.info(f"Switching to fallback provider: {provider_name}-{model_tier}")
            self._current_provider = AIProviderFactory.create_provider(
                model_tier=model_tier,
                provider_name=provider_name
            )
            
            model_info = self._current_provider.get_model_info()
            logger.info(f"Successfully switched to: {model_info['model_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch to {provider_name}-{model_tier}: {e}")
            # Try next provider recursively
            return self._switch_to_next_provider()
    
    def generate_content(self, prompt: str) -> Dict:
        """
        Generate content with automatic fallback on failure
        
        Args:
            prompt: The text prompt to send to the AI model
            
        Returns:
            Dict containing response and token usage information
            
        Raises:
            Exception: If all providers fail
        """
        if not self._current_provider:
            raise Exception("No AI provider available")
        
        last_error = None
        
        # Keep trying with different providers until success or all exhausted
        while True:
            try:
                # Log which provider is being used
                model_info = self._current_provider.get_model_info()
                logger.debug(f"Calling AI provider: {model_info['model_name']}")
                
                # Attempt to generate content
                response = self._current_provider.generate_content(prompt)
                
                # Success - return the response
                return response
                
            except Exception as e:
                last_error = str(e)
                provider_info = self._current_provider.get_model_info()
                logger.warning(f"Provider {provider_info['model_name']} failed: {e}")
                
                # Try switching to next provider
                if not self._switch_to_next_provider():
                    # All providers exhausted
                    raise Exception(f"All providers failed. Last error: {last_error}")
                
                # Continue with next provider
                logger.info(f"Retrying with next provider...")
    
    def get_model_info(self) -> Dict:
        """
        Get information about the current model
        
        Returns:
            Dict containing model info with additional fallback information
        """
        if not self._current_provider:
            return {
                "model_name": "No provider available",
                "provider": "None",
                "fallback_info": {
                    "current_index": self._current_index,
                    "total_providers": len(self.provider_configs),
                    "provider_configs": self.provider_configs
                }
            }
        
        info = self._current_provider.get_model_info()
        
        # Add fallback information
        info["fallback_info"] = {
            "current_index": self._current_index,
            "total_providers": len(self.provider_configs),
            "current_config": self.provider_configs[self._current_index],
            "all_configs": self.provider_configs
        }
        
        return info
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Dict:
        """
        Calculate the cost based on token counts for current provider
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Dict containing cost calculation details
        """
        if not self._current_provider:
            raise Exception("No AI provider available")
            
        return self._current_provider.estimate_cost(input_tokens, output_tokens)
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in the given text using current provider
        
        Args:
            text: The text to count tokens for
            
        Returns:
            Number of tokens
        """
        if not self._current_provider:
            raise Exception("No AI provider available")
            
        return self._current_provider.count_tokens(text)
    
    def reset_to_primary(self):
        """
        Reset to the first (primary) provider in the configuration list
        
        This is useful for starting fresh with a new batch of requests
        """
        logger.info("Resetting to primary provider")
        self._current_index = 0
        self._initialize_provider()
    
    def get_current_provider_info(self) -> Dict:
        """
        Get detailed information about the currently active provider
        
        Returns:
            Dict with current provider details
        """
        if not self._current_provider:
            return {"status": "No provider available"}
        
        provider_name, model_tier = self.provider_configs[self._current_index]
        model_info = self._current_provider.get_model_info()
        
        return {
            "provider_name": provider_name,
            "model_tier": model_tier,
            "model_name": model_info.get("model_name", "Unknown"),
            "provider_index": self._current_index,
            "total_providers": len(self.provider_configs),
            "remaining_fallbacks": len(self.provider_configs) - self._current_index - 1
        }