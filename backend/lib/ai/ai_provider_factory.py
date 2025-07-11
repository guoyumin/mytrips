"""
AI Provider Factory - Creates and manages AI provider instances
"""
import os
import json
import logging
from typing import Optional, Dict
from lib.ai.ai_provider_interface import AIProviderInterface
from lib.ai.providers.gemini_provider import GeminiProvider
from lib.ai.providers.openai_provider import OpenAIProvider
from lib.ai.providers.claude_provider import ClaudeProvider
from lib.ai.providers.gemma3_provider import Gemma3Provider
from lib.ai.providers.deepseek_provider import DeepSeekProvider

logger = logging.getLogger(__name__)


class AIProviderFactory:
    """Factory for creating AI provider instances"""
    
    # Provider mapping by prefix
    PROVIDER_MAPPING = {
        'gemini': GeminiProvider,
        'gpt': OpenAIProvider,
        'o1': OpenAIProvider,
        'o4': OpenAIProvider,
        'claude': ClaudeProvider,
        'gemma3': Gemma3Provider,
        'deepseek': DeepSeekProvider
    }
    
    # Model tier definitions
    MODEL_TIERS = {
        'fast': 'fast',
        'powerful': 'powerful'
    }
    
    @classmethod
    def create_provider(cls, model_tier: str = 'fast', provider_name: Optional[str] = None) -> AIProviderInterface:
        """
        Create an AI provider instance
        
        Args:
            model_tier: 'fast' or 'powerful' to select model performance tier
            provider_name: Optional provider name ('gemini', 'openai', 'claude'). 
                          If None, uses environment variable AI_PROVIDER or defaults to 'gemini'
            
        Returns:
            AI provider instance implementing AIProviderInterface
        """
        # Validate model tier
        if model_tier not in cls.MODEL_TIERS:
            raise ValueError(f"Invalid model tier: {model_tier}. Must be 'fast' or 'powerful'")
        
        # Determine provider
        if not provider_name:
            provider_name = os.getenv('AI_PROVIDER', 'gemini')
        
        provider_name = provider_name.lower()
        
        # Get the provider class
        provider_class = cls._get_provider_by_name(provider_name)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        # Get the actual model name from config
        model_name = cls._get_model_for_tier(provider_name, model_tier)
        
        logger.info(f"Creating {provider_name} provider with {model_tier} model: {model_name}")
        
        # Create and return provider instance
        return provider_class(model_name)
    
    @classmethod
    def _get_provider_by_name(cls, provider_name: str):
        """Get the provider class by provider name"""
        provider_name = provider_name.lower()
        
        # Direct mapping
        if provider_name in cls.PROVIDER_MAPPING:
            return cls.PROVIDER_MAPPING[provider_name]
        
        # Handle 'openai' as alias for 'gpt'
        if provider_name == 'openai':
            return cls.PROVIDER_MAPPING['gpt']
        
        return None
    
    @classmethod
    def _get_model_for_tier(cls, provider_name: str, tier: str) -> str:
        """Get the actual model name for a provider and tier from config"""
        # Map provider names to config files
        config_mapping = {
            'gemini': 'gemini_config.json',
            'openai': 'openai_config.json',
            'gpt': 'openai_config.json',
            'claude': 'claude_config.json',
            'gemma3': 'gemma3_config.json',
            'deepseek': 'deepseek_config.json'
        }
        
        config_file = config_mapping.get(provider_name.lower())
        if not config_file:
            raise ValueError(f"No config mapping for provider: {provider_name}")
        
        # Load config file
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        config_path = os.path.join(project_root, 'config', config_file)
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Get model mapping
            model_mapping = config.get('model_mapping', {})
            if tier not in model_mapping:
                raise ValueError(f"No {tier} model mapping found for {provider_name} in {config_path}")
            
            return model_mapping[tier]
            
        except Exception as e:
            logger.error(f"Error loading config for {provider_name}: {e}")
            raise
    
    @classmethod
    def get_available_providers(cls) -> Dict[str, Dict[str, str]]:
        """Get available providers and their model tiers"""
        providers = {}
        
        for provider_name in ['gemini', 'openai', 'claude', 'gemma3', 'deepseek']:
            try:
                fast_model = cls._get_model_for_tier(provider_name, 'fast')
                powerful_model = cls._get_model_for_tier(provider_name, 'powerful')
                providers[provider_name] = {
                    'fast': fast_model,
                    'powerful': powerful_model
                }
            except Exception as e:
                logger.warning(f"Could not load models for {provider_name}: {e}")
        
        return providers
    
    @classmethod
    def create_provider_direct(cls, model_name: str) -> AIProviderInterface:
        """
        Create a provider with a specific model name (bypasses tier abstraction)
        For backward compatibility or specific model requirements
        """
        logger.info(f"Creating AI provider for specific model: {model_name}")
        
        # Determine provider from model name
        for prefix, provider_class in cls.PROVIDER_MAPPING.items():
            if model_name.startswith(prefix):
                return provider_class(model_name)
        
        # Special handling for o1 and o4 models
        if model_name.startswith('o1') or model_name.startswith('o4'):
            return OpenAIProvider(model_name)
        
        # Special handling for gemma models
        if model_name.startswith('gemma'):
            return Gemma3Provider(model_name)
        
        # Special handling for deepseek models
        if model_name.startswith('deepseek'):
            return DeepSeekProvider(model_name)
        
        raise ValueError(f"Cannot determine provider for model: {model_name}")