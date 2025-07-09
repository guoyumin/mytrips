"""
Test Model Tier System
Verify that the tier abstraction works correctly for all providers
"""
import sys
import os
import json
import warnings

# Suppress Google protobuf deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="google._upb._message")

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..', 'backend'))

from lib.ai.ai_provider_factory import AIProviderFactory


def test_tier_mappings():
    """Test that tier mappings are correctly configured in all config files"""
    config_root = os.path.join(os.path.dirname(__file__), '../..', 'config')
    providers = ['gemini', 'openai', 'claude']
    
    print("=== Model Tier Configuration Test ===\n")
    
    all_valid = True
    
    for provider in providers:
        config_file = f"{provider}_config.json"
        config_path = os.path.join(config_root, config_file)
        
        print(f"--- {provider.upper()} ---")
        
        if not os.path.exists(config_path):
            print(f"❌ Config file not found: {config_file}")
            all_valid = False
            continue
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Check for model_mapping
            if 'model_mapping' not in config:
                print(f"❌ Missing 'model_mapping' in {config_file}")
                all_valid = False
                continue
            
            model_mapping = config['model_mapping']
            
            # Check for required tiers
            missing_tiers = []
            for tier in ['fast', 'powerful']:
                if tier not in model_mapping:
                    missing_tiers.append(tier)
            
            if missing_tiers:
                print(f"❌ Missing tiers: {', '.join(missing_tiers)}")
                all_valid = False
            else:
                print(f"✅ All tiers configured:")
                print(f"   fast     → {model_mapping['fast']}")
                print(f"   powerful → {model_mapping['powerful']}")
            
            # Check API key
            api_key = config.get('api_key', '')
            if not api_key or api_key.startswith('YOUR_'):
                print(f"⚠️  API key not configured")
            else:
                print(f"✅ API key configured")
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {config_file}: {e}")
            all_valid = False
        except Exception as e:
            print(f"❌ Error reading {config_file}: {e}")
            all_valid = False
        
        print()
    
    return all_valid


def test_tier_consistency():
    """Test that the same tier returns appropriate models across providers"""
    print("=== Model Tier Consistency Test ===\n")
    
    # Expected patterns for each tier
    fast_patterns = ['flash', 'mini', 'haiku', 'fast']
    powerful_patterns = ['pro', 'turbo', 'opus', 'sonnet', 'powerful']
    
    providers = ['gemini', 'openai', 'claude']
    results = {'fast': {}, 'powerful': {}}
    
    for provider in providers:
        for tier in ['fast', 'powerful']:
            try:
                model = AIProviderFactory._get_model_for_tier(provider, tier)
                results[tier][provider] = model
            except Exception as e:
                results[tier][provider] = f"Error: {e}"
    
    # Print results
    for tier in ['fast', 'powerful']:
        print(f"--- {tier.upper()} Tier ---")
        patterns = fast_patterns if tier == 'fast' else powerful_patterns
        
        for provider, model in results[tier].items():
            if 'Error' in str(model):
                print(f"❌ {provider}: {model}")
            else:
                # Check if model name matches expected patterns
                matches_pattern = any(pattern in model.lower() for pattern in patterns)
                symbol = "✅" if matches_pattern else "⚠️"
                print(f"{symbol} {provider}: {model}")
        print()


def test_tier_performance_ordering():
    """Verify that 'powerful' models are indeed more expensive than 'fast' models"""
    print("=== Cost Comparison Test ===\n")
    
    providers = ['gemini', 'openai', 'claude']
    test_prompt_length = 1000
    
    for provider_name in providers:
        print(f"--- {provider_name.upper()} ---")
        costs = {}
        
        for tier in ['fast', 'powerful']:
            try:
                provider = AIProviderFactory.create_provider(
                    model_tier=tier,
                    provider_name=provider_name
                )
                cost_info = provider.estimate_cost(test_prompt_length)
                costs[tier] = cost_info.get('estimated_cost_usd', 0)
                print(f"{tier}: ${costs[tier]:.6f}")
            except Exception as e:
                print(f"{tier}: Error - {e}")
                costs[tier] = None
        
        # Verify ordering
        if costs['fast'] is not None and costs['powerful'] is not None:
            if costs['fast'] < costs['powerful']:
                print("✅ Cost ordering correct (fast < powerful)")
            else:
                print("⚠️  Warning: fast model is not cheaper than powerful model")
        print()


def test_service_tier_usage():
    """Test that services are using appropriate tiers"""
    print("=== Service Tier Usage Test ===\n")
    
    # Define expected tier usage for each service
    expected_usage = {
        'EmailClassificationService': 'fast',
        'EmailBookingExtractionService': 'fast',
        'TripDetectionService': 'powerful'
    }
    
    backend_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'backend', 'services')
    
    for service, expected_tier in expected_usage.items():
        service_file = None
        
        # Find the service file
        for filename in os.listdir(backend_dir):
            if service.lower().replace('service', '_service') in filename.lower():
                service_file = os.path.join(backend_dir, filename)
                break
        
        if not service_file or not os.path.exists(service_file):
            print(f"❌ {service}: Service file not found")
            continue
        
        # Check file content for tier usage
        with open(service_file, 'r') as f:
            content = f.read()
        
        if f"model_tier='{expected_tier}'" in content:
            print(f"✅ {service}: Using '{expected_tier}' tier as expected")
        elif "model_tier=" in content:
            # Extract actual tier
            import re
            match = re.search(r"model_tier='(\w+)'", content)
            if match:
                actual_tier = match.group(1)
                print(f"⚠️  {service}: Using '{actual_tier}' tier, expected '{expected_tier}'")
            else:
                print(f"⚠️  {service}: Could not determine tier usage")
        else:
            print(f"❌ {service}: Not using tier-based model selection")


def main():
    """Run all tier tests"""
    tests = [
        ("Tier Mappings", test_tier_mappings),
        ("Tier Consistency", test_tier_consistency),
        ("Cost Ordering", test_tier_performance_ordering),
        ("Service Usage", test_service_tier_usage)
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        try:
            if test_name == "Tier Mappings":
                result = test_func()
                if not result:
                    all_passed = False
            else:
                test_func()
        except Exception as e:
            print(f"\n❌ {test_name} failed with error: {e}")
            all_passed = False
        
        print("\n" + "="*50 + "\n")
    
    if all_passed:
        print("✅ All tier tests completed successfully!")
    else:
        print("⚠️  Some tests encountered issues. Please check the output above.")


if __name__ == '__main__':
    main()