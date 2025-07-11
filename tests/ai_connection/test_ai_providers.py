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
            'claude': ['fast', 'powerful'],
            'gemma3': ['fast', 'powerful'],
            'deepseek': ['fast', 'powerful']
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
        
        # Load Gemma3 models
        gemma3_config_path = os.path.join(config_root, 'gemma3_config.json')
        if os.path.exists(gemma3_config_path):
            with open(gemma3_config_path, 'r') as f:
                config = json.load(f)
                models['gemma3'] = config.get('model_mapping', {})
        
        # Load DeepSeek models
        deepseek_config_path = os.path.join(config_root, 'deepseek_config.json')
        if os.path.exists(deepseek_config_path):
            with open(deepseek_config_path, 'r') as f:
                config = json.load(f)
                models['deepseek'] = config.get('model_mapping', {})
        
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
                    
                    # Use legacy method for backward compatibility
                    response = provider.generate_content_simple(self.TEST_PROMPT)
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
    
    
    def test_cost_estimation(self, provider_configs):
        """Test cost estimation for all providers"""
        results = []
        test_input_tokens = 250  # About 1000 characters
        test_output_tokens = 500  # Estimated output
        
        for provider_name, tiers in provider_configs.items():
            for tier in tiers:
                try:
                    provider = AIProviderFactory.create_provider(
                        model_tier=tier,
                        provider_name=provider_name
                    )
                    
                    cost_info = provider.estimate_cost(test_input_tokens, test_output_tokens)
                    
                    results.append({
                        'provider': provider_name,
                        'tier': tier,
                        'model': provider.get_model_info().get('model_name', 'Unknown'),
                        'estimated_cost_usd': cost_info.get('estimated_cost_usd', 0),
                        'input_cost_usd': cost_info.get('input_cost_usd', 0),
                        'output_cost_usd': cost_info.get('output_cost_usd', 0),
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
        print(f"\n=== Cost Estimation Results ({test_input_tokens} input tokens, {test_output_tokens} output tokens) ===")
        for result in results:
            if result['status'] == 'SUCCESS':
                print(f"{result['provider']}-{result['tier']} ({result['model']}): "
                      f"${result['estimated_cost_usd']:.6f} "
                      f"(in: ${result['input_cost_usd']:.6f}, out: ${result['output_cost_usd']:.6f})")
            else:
                print(f"{result['provider']}-{result['tier']}: Failed - {result.get('error', 'Unknown error')}")
    
    def test_token_counting_and_pricing(self, provider_configs):
        """Test token counting functionality and pricing accuracy"""
        results = []
        test_prompt = """Analyze this travel itinerary:
        - Flight from Zurich to Paris on March 15, 2024
        - Stay at Hotel Le Meurice for 3 nights
        - Return flight on March 18, 2024
        Please extract key travel information."""
        
        for provider_name, tiers in provider_configs.items():
            for tier in tiers:
                try:
                    provider = AIProviderFactory.create_provider(
                        model_tier=tier,
                        provider_name=provider_name
                    )
                    
                    # Test generate_content with token info
                    print(f"\n🔍 Testing token counting for {provider_name}-{tier}")
                    response = provider.generate_content(test_prompt)
                    
                    # Verify response structure
                    assert isinstance(response, dict), "Response should be a dictionary"
                    assert all(key in response for key in ['content', 'input_tokens', 'output_tokens', 'total_tokens', 'estimated_cost_usd'])
                    
                    results.append({
                        'provider': provider_name,
                        'tier': tier,
                        'model': provider.get_model_info().get('model_name', 'Unknown'),
                        'input_tokens': response['input_tokens'],
                        'output_tokens': response['output_tokens'],
                        'total_tokens': response['total_tokens'],
                        'cost_usd': response['estimated_cost_usd'],
                        'content_length': len(response['content']),
                        'status': 'SUCCESS'
                    })
                    
                    # Test optional count_tokens method
                    try:
                        token_count = provider.count_tokens(test_prompt)
                        print(f"  count_tokens result: {token_count} tokens")
                    except NotImplementedError:
                        print(f"  count_tokens not implemented (optional)")
                    
                except Exception as e:
                    results.append({
                        'provider': provider_name,
                        'tier': tier,
                        'status': 'FAILED',
                        'error': str(e)
                    })
        
        # Print token counting results
        print("\n=== Token Counting and Pricing Results ===")
        for result in results:
            if result['status'] == 'SUCCESS':
                print(f"\n{result['provider']}-{result['tier']} ({result['model']}):")
                print(f"  Input tokens: {result['input_tokens']}")
                print(f"  Output tokens: {result['output_tokens']}")
                print(f"  Total tokens: {result['total_tokens']}")
                print(f"  Cost: ${result['cost_usd']:.6f}")
                print(f"  Response length: {result['content_length']} chars")
            else:
                print(f"\n{result['provider']}-{result['tier']}: Failed - {result.get('error', 'Unknown error')}")
        
        # Verify token counts are reasonable
        successful_results = [r for r in results if r['status'] == 'SUCCESS']
        if successful_results:
            # Prompt is about 50 words, should be 30-100 tokens
            for result in successful_results:
                assert 20 < result['input_tokens'] < 150, f"Input tokens {result['input_tokens']} seems unreasonable"
                assert result['output_tokens'] > 0, "Output tokens should be positive"
                assert result['total_tokens'] == result['input_tokens'] + result['output_tokens']
                # Local models (gemma3, deepseek) have zero cost, others should have positive cost
                if result['provider'] in ['gemma3', 'deepseek']:
                    assert result['cost_usd'] == 0.0, f"{result['provider']} should have zero cost, got ${result['cost_usd']}"
                else:
                    assert 0 < result['cost_usd'] < 1.0, f"Cost ${result['cost_usd']} seems unreasonable"
    
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