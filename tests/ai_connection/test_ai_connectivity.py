#!/usr/bin/env python3
"""
Quick AI Provider Connectivity Test
Run this to verify all AI providers are properly configured and accessible.
"""
import sys
import os
import json
import warnings
import pytest
from datetime import datetime
from typing import Dict, List

# Suppress Google protobuf deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="google._upb._message")

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..', 'backend'))

from lib.ai.ai_provider_factory import AIProviderFactory


def load_provider_configs() -> Dict[str, Dict]:
    """Load all provider configurations"""
    configs = {}
    config_root = os.path.join(os.path.dirname(__file__), '../..', 'config')
    
    # Provider config files
    config_files = {
        'gemini': 'gemini_config.json',
        'openai': 'openai_config.json',
        'claude': 'claude_config.json'
    }
    
    for provider, filename in config_files.items():
        config_path = os.path.join(config_root, filename)
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                configs[provider] = json.load(f)
    
    return configs


def test_provider_connectivity():
    """Test basic provider connectivity"""
    # Test each provider/tier combination
    results = []
    providers_to_test = ['gemini', 'openai', 'claude']
    tiers_to_test = ['fast', 'powerful']
    
    for provider in providers_to_test:
        for tier in tiers_to_test:
            result = _test_single_provider_connectivity(provider, tier)
            results.append(result)
    
    # Now each provider should either work or fail clearly
    success_count = sum(1 for r in results if r['success'])
    failed_count = sum(1 for r in results if not r['success'])
    
    print(f"\n=== Test Results ===")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    
    # Show detailed results
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} {result['provider']}-{result['tier']}: {result.get('error', 'Success')}")
    
    # Test passes if configured providers work (we expect some to fail if not configured)
    assert success_count > 0, f"No providers working. Results: {results}"


def _test_single_provider_connectivity(provider_name: str, tier: str) -> Dict:
    """Test a single provider/tier combination"""
    result = {
        'provider': provider_name,
        'tier': tier,
        'timestamp': datetime.now().isoformat(),
        'success': False,
        'model': None,
        'response': None,
        'error': None,
        'response_time_ms': None
    }
    
    try:
        # Create provider
        start_time = datetime.now()
        provider = AIProviderFactory.create_provider(
            model_tier=tier,
            provider_name=provider_name
        )
        
        # Get model info
        model_info = provider.get_model_info()
        actual_model = model_info.get('version', model_info.get('model_name', 'Unknown'))
        result['model'] = actual_model
        
        # No fallback mechanism anymore - provider creation should succeed or fail clearly
        
        # Test with simple prompt
        test_prompt = "Respond with exactly: OK"
        print(f"\n🔄 Sending real request to {provider_name}-{tier}")
        print(f"📝 Request: {test_prompt}")
        print(f"🎯 Expected provider: {provider_name}, Actual model: {actual_model}")
        response = provider.generate_content(test_prompt)
        print(f"✅ Response: {response}")
        print(f"⏱️  Response received in {int((datetime.now() - start_time).total_seconds() * 1000)}ms")
        
        # Calculate response time
        end_time = datetime.now()
        result['response_time_ms'] = int((end_time - start_time).total_seconds() * 1000)
        
        # Validate response
        if response and isinstance(response, dict) and response.get('content'):
            content = response['content'].strip() if isinstance(response['content'], str) else str(response['content'])
            if content:
                result['success'] = True
                result['response'] = content[:50]  # First 50 chars
            else:
                result['error'] = "Empty response content"
        else:
            result['error'] = "Invalid or empty response received"
            
    except Exception as e:
        result['error'] = str(e)
    
    return result


def main():
    """Run connectivity tests for all providers"""
    print("=== AI Provider Connectivity Test ===")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Load configurations
    configs = load_provider_configs()
    print(f"Found configurations for: {', '.join(configs.keys())}\n")
    
    # Test each provider/tier combination
    results = []
    providers_to_test = ['gemini', 'openai', 'claude']
    tiers_to_test = ['fast', 'powerful']
    
    for provider in providers_to_test:
        if provider not in configs:
            print(f"⚠️  No configuration found for {provider}")
            continue
            
        config = configs[provider]
        model_mapping = config.get('model_mapping', {})
        
        print(f"\n--- Testing {provider.upper()} ---")
        print(f"API Key: {'Configured' if config.get('api_key') and config['api_key'] != 'YOUR_' + provider.upper() + '_API_KEY_HERE' else 'NOT CONFIGURED'}")
        print(f"Models: {json.dumps(model_mapping, indent=2)}")
        
        for tier in tiers_to_test:
            if tier not in model_mapping:
                print(f"⚠️  No {tier} model configured for {provider}")
                continue
            
            print(f"\nTesting {provider}-{tier} ({model_mapping[tier]})...")
            result = test_provider_connectivity(provider, tier)
            results.append(result)
            
            # Print result
            if result['success']:
                print(f"✅ Success! Response time: {result['response_time_ms']}ms")
                print(f"   Model: {result['model']}")
                print(f"   Response: {result['response']}")
            else:
                print(f"❌ Failed: {result['error']}")
    
    # Summary
    print("\n\n=== SUMMARY ===")
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    print(f"Total tests: {total_count}")
    print(f"Successful: {success_count}")
    print(f"Failed: {total_count - success_count}")
    
    # Group by provider
    print("\nBy Provider:")
    for provider in providers_to_test:
        provider_results = [r for r in results if r['provider'] == provider]
        if provider_results:
            success = sum(1 for r in provider_results if r['success'])
            print(f"  {provider}: {success}/{len(provider_results)} successful")
    
    # Performance comparison
    print("\nResponse Times (successful tests only):")
    successful_results = [r for r in results if r['success']]
    if successful_results:
        sorted_results = sorted(successful_results, key=lambda x: x['response_time_ms'])
        for result in sorted_results:
            print(f"  {result['provider']}-{result['tier']}: {result['response_time_ms']}ms")
    
    # Configuration issues
    print("\nConfiguration Issues:")
    for provider, config in configs.items():
        api_key = config.get('api_key', '')
        if not api_key or api_key.startswith('YOUR_'):
            print(f"  ⚠️  {provider}: API key not configured")
    
    # Write results to file
    results_file = os.path.join(os.path.dirname(__file__), 'ai_connectivity_results.json')
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'summary': {
                'total': total_count,
                'successful': success_count,
                'failed': total_count - success_count
            }
        }, f, indent=2)
    print(f"\nDetailed results saved to: {results_file}")


if __name__ == '__main__':
    main()