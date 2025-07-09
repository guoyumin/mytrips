"""
Unit tests for AI Provider Factory
"""
import pytest
import sys
import os
import json
import warnings
from unittest.mock import Mock, patch, mock_open

# Suppress Google protobuf deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="google._upb._message")

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..', 'backend'))

from lib.ai.ai_provider_factory import AIProviderFactory
from lib.ai.ai_provider_interface import AIProviderInterface
from lib.ai.providers.gemini_provider import GeminiProvider
from lib.ai.providers.openai_provider import OpenAIProvider
from lib.ai.providers.claude_provider import ClaudeProvider


class TestAIProviderFactory:
    """Test suite for AI Provider Factory"""
    
    def test_provider_mapping(self):
        """Test that provider mapping is correctly configured"""
        assert 'gemini' in AIProviderFactory.PROVIDER_MAPPING
        assert 'gpt' in AIProviderFactory.PROVIDER_MAPPING
        assert 'claude' in AIProviderFactory.PROVIDER_MAPPING
        assert AIProviderFactory.PROVIDER_MAPPING['gemini'] == GeminiProvider
        assert AIProviderFactory.PROVIDER_MAPPING['gpt'] == OpenAIProvider
        assert AIProviderFactory.PROVIDER_MAPPING['claude'] == ClaudeProvider
    
    def test_model_tiers(self):
        """Test that model tiers are defined"""
        assert 'fast' in AIProviderFactory.MODEL_TIERS
        assert 'powerful' in AIProviderFactory.MODEL_TIERS
    
    def test_get_provider_by_name(self):
        """Test provider class retrieval by name"""
        assert AIProviderFactory._get_provider_by_name('gemini') == GeminiProvider
        assert AIProviderFactory._get_provider_by_name('openai') == OpenAIProvider
        assert AIProviderFactory._get_provider_by_name('claude') == ClaudeProvider
        assert AIProviderFactory._get_provider_by_name('invalid') is None
    
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        'api_key': 'test_key',
        'model': 'test_model',
        'model_mapping': {
            'fast': 'test-fast-model',
            'powerful': 'test-powerful-model'
        }
    }))
    def test_get_model_for_tier(self, mock_file):
        """Test model retrieval for tier from config"""
        # Test Gemini
        model = AIProviderFactory._get_model_for_tier('gemini', 'fast')
        assert model == 'test-fast-model'
        
        model = AIProviderFactory._get_model_for_tier('gemini', 'powerful')
        assert model == 'test-powerful-model'
    
    def test_get_model_for_tier_fallback(self):
        """Test fallback when config file doesn't exist"""
        with patch('builtins.open', side_effect=FileNotFoundError):
            # Should use hardcoded fallbacks
            model = AIProviderFactory._get_model_for_tier('gemini', 'fast')
            assert model == 'gemini-2.5-flash'
            
            model = AIProviderFactory._get_model_for_tier('openai', 'powerful')
            assert model == 'gpt-4-turbo-preview'
            
            model = AIProviderFactory._get_model_for_tier('claude', 'fast')
            assert model == 'claude-3-5-haiku-20241022'
    
    @patch.object(GeminiProvider, '__init__', return_value=None)
    def test_create_provider_default(self, mock_gemini_init):
        """Test creating provider with defaults"""
        with patch.dict(os.environ, {}, clear=True):
            # Mock the config loading
            with patch.object(AIProviderFactory, '_get_model_for_tier', return_value='gemini-2.5-flash'):
                provider = AIProviderFactory.create_provider()
                mock_gemini_init.assert_called_once_with('gemini-2.5-flash')
    
    @patch.object(OpenAIProvider, '__init__', return_value=None)
    def test_create_provider_with_env(self, mock_openai_init):
        """Test creating provider with environment variable"""
        with patch.dict(os.environ, {'AI_PROVIDER': 'openai'}):
            with patch.object(AIProviderFactory, '_get_model_for_tier', return_value='gpt-4o-mini'):
                provider = AIProviderFactory.create_provider(model_tier='fast')
                mock_openai_init.assert_called_once_with('gpt-4o-mini')
    
    def test_create_provider_invalid_tier(self):
        """Test creating provider with invalid tier"""
        with pytest.raises(ValueError, match="Invalid model tier"):
            AIProviderFactory.create_provider(model_tier='invalid')
    
    def test_create_provider_invalid_provider(self):
        """Test creating provider with invalid provider name raises error"""
        # Invalid provider should raise error directly
        with pytest.raises(ValueError, match="Unknown provider"):
            AIProviderFactory.create_provider(provider_name='invalid_provider')
    
    def test_provider_creation_failure(self):
        """Test that provider creation failure raises error directly"""
        # Test that if a provider fails to initialize, it raises the error directly
        with patch.object(GeminiProvider, '__init__', side_effect=Exception("Init failed")):
            with patch.object(AIProviderFactory, '_get_model_for_tier', return_value='test-model'):
                with pytest.raises(Exception, match="Init failed"):
                    AIProviderFactory.create_provider(provider_name='gemini')
    
    def test_create_provider_direct_gemini(self):
        """Test direct model creation for Gemini"""
        with patch.object(GeminiProvider, '__init__', return_value=None) as mock_init:
            provider = AIProviderFactory.create_provider_direct('gemini-2.5-flash')
            mock_init.assert_called_once_with('gemini-2.5-flash')
    
    def test_create_provider_direct_openai(self):
        """Test direct model creation for OpenAI"""
        with patch.object(OpenAIProvider, '__init__', return_value=None) as mock_init:
            provider = AIProviderFactory.create_provider_direct('gpt-4')
            mock_init.assert_called_once_with('gpt-4')
    
    def test_create_provider_direct_claude(self):
        """Test direct model creation for Claude"""
        with patch.object(ClaudeProvider, '__init__', return_value=None) as mock_init:
            provider = AIProviderFactory.create_provider_direct('claude-3-opus-20240229')
            mock_init.assert_called_once_with('claude-3-opus-20240229')
    
    def test_create_provider_direct_o4_model(self):
        """Test direct model creation for o4 models (OpenAI)"""
        with patch.object(OpenAIProvider, '__init__', return_value=None) as mock_init:
            provider = AIProviderFactory.create_provider_direct('o4-mini')
            mock_init.assert_called_once_with('o4-mini')
    
    def test_create_provider_direct_invalid(self):
        """Test direct model creation with invalid model"""
        with pytest.raises(ValueError, match="Cannot determine provider"):
            AIProviderFactory.create_provider_direct('invalid-model-name')
    
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        'model_mapping': {'fast': 'test-fast', 'powerful': 'test-powerful'}
    }))
    def test_get_available_providers(self, mock_file):
        """Test getting available providers"""
        providers = AIProviderFactory.get_available_providers()
        
        assert isinstance(providers, dict)
        # Should have entries for providers that have config files
        assert len(providers) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])