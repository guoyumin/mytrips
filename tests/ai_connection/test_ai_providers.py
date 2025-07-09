"""
Test AI Provider Connectivity and Model Availability
"""
import pytest
import sys
import os
import json
import warnings
from typing import Dict, List, Tuple

# Suppress Google protobuf deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="google._upb._message")

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..', 'backend'))

from lib.ai.ai_provider_factory import AIProviderFactory
from lib.ai.ai_provider_interface import AIProviderInterface


class TestAIProviders:
    """Test suite for AI provider connectivity and model availability"""
    
    # Test prompt - simple and universal
    TEST_PROMPT = "Say 'Hello World' in exactly two words."
    
    @pytest.fixture
    def provider_configs(self) -> Dict[str, List[str]]:
        """Get all provider configurations"""
        return {
            'gemini': ['fast', 'powerful'],
            'openai': ['fast', 'powerful'],
            'claude': ['fast', 'powerful']
        }
    
    @pytest.fixture
    def all_models(self) -> Dict[str, Dict[str, str]]:
        """Get all specific models from config files"""
        models = {}
        config_root = os.path.join(os.path.dirname(__file__), '../..', 'config')
        
        # Load Gemini models
        gemini_config_path = os.path.join(config_root, 'gemini_config.json')
        if os.path.exists(gemini_config_path):
            with open(gemini_config_path, 'r') as f:
                config = json.load(f)
                models['gemini'] = config.get('model_mapping', {})
        
        # Load OpenAI models
        openai_config_path = os.path.join(config_root, 'openai_config.json')
        if os.path.exists(openai_config_path):
            with open(openai_config_path, 'r') as f:
                config = json.load(f)
                models['openai'] = config.get('model_mapping', {})
        
        # Load Claude models
        claude_config_path = os.path.join(config_root, 'claude_config.json')
        if os.path.exists(claude_config_path):
            with open(claude_config_path, 'r') as f:
                config = json.load(f)
                models['claude'] = config.get('model_mapping', {})
        
        return models
    
    def test_provider_factory_tier_creation(self, provider_configs):
        """Test creating providers using tier system"""
        results = []
        
        for provider_name, tiers in provider_configs.items():
            for tier in tiers:
                try:
                    provider = AIProviderFactory.create_provider(
                        model_tier=tier,
                        provider_name=provider_name
                    )
                    model_info = provider.get_model_info()
                    results.append({
                        'provider': provider_name,
                        'tier': tier,
                        'model': model_info.get('model_name', 'Unknown'),
                        'status': 'SUCCESS',
                        'error': None
                    })
                except Exception as e:
                    results.append({
                        'provider': provider_name,
                        'tier': tier,
                        'model': None,
                        'status': 'FAILED',
                        'error': str(e)
                    })
        
        # Print results
        print("\n=== Provider Factory Tier Creation Test Results ===")
        for result in results:
            status_symbol = "✓" if result['status'] == 'SUCCESS' else "✗"
            print(f"{status_symbol} {result['provider']}-{result['tier']}: {result['model'] or result['error']}")
        
        # At least some providers should work
        success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
        assert success_count > 0, "No providers could be created successfully"
    
    def test_connectivity_all_providers(self, provider_configs):
        """Test actual connectivity for all providers"""
        results = []
        
        for provider_name, tiers in provider_configs.items():
            for tier in tiers:
                try:
                    # Create provider
                    provider = AIProviderFactory.create_provider(
                        model_tier=tier,
                        provider_name=provider_name
                    )
                    
                    # Get model info - no fallback mechanism anymore
                    model_info = provider.get_model_info()
                    actual_model = model_info.get('model_name', 'Unknown')
                    
                    # Test connectivity with simple prompt
                    print(f"\n🔄 Sending real request to {provider_name}-{tier}")
                    print(f"📝 Request: {self.TEST_PROMPT}")
                    print(f"🎯 Expected provider: {provider_name}, Actual model: {actual_model}")
                    response = provider.generate_content(self.TEST_PROMPT)
                    print(f"✅ Response: {response}")
                    
                    # Validate response
                    is_valid = response and len(response.strip()) > 0
                    
                    results.append({
                        'provider': provider_name,
                        'tier': tier,
                        'model': actual_model,
                        'status': 'SUCCESS' if is_valid else 'INVALID_RESPONSE',
                        'response': response[:100] if response else None,
                        'error': None if is_valid else 'Empty or invalid response'
                    })
                    
                except Exception as e:
                    results.append({
                        'provider': provider_name,
                        'tier': tier,
                        'model': None,
                        'status': 'FAILED',
                        'response': None,
                        'error': str(e)
                    })
        
        # Print detailed results
        print("\n=== AI Provider Connectivity Test Results ===")
        for result in results:
            status_symbol = "✓" if result['status'] == 'SUCCESS' else "✗"
            print(f"\n{status_symbol} {result['provider']}-{result['tier']}:")
            print(f"  Model: {result['model'] or 'N/A'}")
            print(f"  Status: {result['status']}")
            if result['response']:
                print(f"  Response: {result['response']}")
            if result['error']:
                print(f"  Error: {result['error']}")
        
        # Summary
        success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
        failed_count = sum(1 for r in results if r['status'] == 'FAILED')
        total_count = len(results)
        print(f"\n=== Summary: {success_count}/{total_count} tests passed ===")
        
        # Test passes if at least one provider works (we expect some to fail if not configured)
        assert success_count > 0, f"No providers working. Results: {results}"
    
    def test_specific_models_direct(self, all_models):
        """Test creating providers with specific model names directly"""
        results = []
        
        for provider_name, model_mapping in all_models.items():
            for tier, model_name in model_mapping.items():
                try:
                    # Create provider with specific model
                    provider = AIProviderFactory.create_provider_direct(model_name)
                    
                    # Test connectivity
                    print(f"\n🔄 Sending real request to {provider_name} model {model_name}")
                    print(f"📝 Request: {self.TEST_PROMPT}")
                    response = provider.generate_content(self.TEST_PROMPT)
                    print(f"✅ Response: {response}")
                    is_valid = response and len(response.strip()) > 0
                    
                    results.append({
                        'provider': provider_name,
                        'model': model_name,
                        'tier': tier,
                        'status': 'SUCCESS' if is_valid else 'INVALID_RESPONSE',
                        'response': response[:100] if response else None,
                        'error': None if is_valid else 'Empty or invalid response'
                    })
                    
                except Exception as e:
                    results.append({
                        'provider': provider_name,
                        'model': model_name,
                        'tier': tier,
                        'status': 'FAILED',
                        'response': None,
                        'error': str(e)
                    })
        
        # Print results
        print("\n=== Direct Model Creation Test Results ===")
        for result in results:
            status_symbol = "✓" if result['status'] == 'SUCCESS' else "✗"
            print(f"{status_symbol} {result['model']} ({result['provider']}-{result['tier']}): {result['status']}")
            if result['error']:
                print(f"  Error: {result['error']}")
    
    def test_cost_estimation(self, provider_configs):
        """Test cost estimation for all providers"""
        results = []
        test_prompt_length = 1000  # Characters
        
        for provider_name, tiers in provider_configs.items():
            for tier in tiers:
                try:
                    provider = AIProviderFactory.create_provider(
                        model_tier=tier,
                        provider_name=provider_name
                    )
                    
                    cost_info = provider.estimate_cost(test_prompt_length)
                    
                    results.append({
                        'provider': provider_name,
                        'tier': tier,
                        'model': provider.get_model_info().get('model_name', 'Unknown'),
                        'estimated_cost_usd': cost_info.get('estimated_cost_usd', 0),
                        'input_tokens': cost_info.get('input_tokens', 0),
                        'output_tokens': cost_info.get('output_tokens', 0),
                        'status': 'SUCCESS'
                    })
                    
                except Exception as e:
                    results.append({
                        'provider': provider_name,
                        'tier': tier,
                        'status': 'FAILED',
                        'error': str(e)
                    })
        
        # Print cost comparison
        print("\n=== Cost Estimation Results (1000 chars) ===")
        for result in results:
            if result['status'] == 'SUCCESS':
                print(f"{result['provider']}-{result['tier']} ({result['model']}): ${result['estimated_cost_usd']:.6f}")
            else:
                print(f"{result['provider']}-{result['tier']}: Failed - {result.get('error', 'Unknown error')}")
    
    def test_no_fallback_mechanism(self):
        """Test that invalid provider raises error without fallback"""
        # Invalid provider should raise error directly
        with pytest.raises(ValueError, match="Unknown provider"):
            AIProviderFactory.create_provider(
                model_tier='fast',
                provider_name='invalid_provider'
            )
        
        print("\n✅ Invalid provider correctly raised ValueError without fallback")


if __name__ == '__main__':
    # Run tests with verbose output
    pytest.main([__file__, '-v', '-s'])