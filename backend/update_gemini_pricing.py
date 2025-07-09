#!/usr/bin/env python3
"""
Update Gemini pricing configuration
"""
import os
import json
import sys
from datetime import datetime

def update_pricing_config():
    """Update pricing configuration with latest values"""
    
    # Get config path
    project_root = os.path.dirname(os.path.dirname(__file__))
    config_path = os.path.join(project_root, 'config', 'gemini_pricing.json')
    
    # Latest pricing from https://ai.google.dev/gemini-api/docs/pricing
    updated_pricing = {
        "pricing": {
            "gemini-2.5-flash": {
                "input_cost_per_1m_tokens": 0.30,
                "output_cost_per_1m_tokens": 2.50,
                "description": "Most cost-effective model for simple tasks",
                "free_tier": True,
                "updated": datetime.now().strftime("%Y-%m-%d")
            },
            "gemini-2.5-pro": {
                "input_cost_per_1m_tokens_small": 1.25,
                "input_cost_per_1m_tokens_large": 2.50,
                "output_cost_per_1m_tokens_small": 10.00,
                "output_cost_per_1m_tokens_large": 15.00,
                "context_threshold": 200000,
                "description": "High-performance model for complex analysis",
                "free_tier": True,
                "updated": datetime.now().strftime("%Y-%m-%d")
            },
            "gemini-1.5-flash": {
                "input_cost_per_1m_tokens": 0.075,
                "output_cost_per_1m_tokens": 0.30,
                "description": "Legacy flash model",
                "free_tier": True,
                "updated": datetime.now().strftime("%Y-%m-%d")
            },
            "gemini-2.0-flash": {
                "input_cost_per_1m_tokens": 0.10,
                "output_cost_per_1m_tokens": 0.40,
                "description": "Latest flash model",
                "free_tier": True,
                "updated": datetime.now().strftime("%Y-%m-%d")
            }
        },
        "currency": "USD",
        "notes": [
            "Prices are per 1 million tokens",
            "Gemini 2.5 Pro has tiered pricing based on context size (≤200k vs >200k tokens)",
            "Free tier available with rate limits in Google AI Studio",
            "Prices subject to change - check official documentation"
        ],
        "source": "https://ai.google.dev/gemini-api/docs/pricing",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        # Load existing config if it exists
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                existing_config = json.load(f)
            print(f"Existing config found, updating...")
        else:
            existing_config = {}
            print(f"Creating new pricing config...")
        
        # Write updated config
        with open(config_path, 'w') as f:
            json.dump(updated_pricing, f, indent=2)
        
        print(f"✅ Pricing configuration updated successfully!")
        print(f"Config location: {config_path}")
        print(f"Last updated: {updated_pricing['last_updated']}")
        
        # Display current pricing
        print("\n📊 Current Pricing (per 1M tokens):")
        for model, pricing in updated_pricing['pricing'].items():
            print(f"\n{model}:")
            if 'input_cost_per_1m_tokens' in pricing:
                print(f"  Input: ${pricing['input_cost_per_1m_tokens']:.2f}")
                print(f"  Output: ${pricing['output_cost_per_1m_tokens']:.2f}")
            else:
                print(f"  Input (≤200k): ${pricing['input_cost_per_1m_tokens_small']:.2f}")
                print(f"  Input (>200k): ${pricing['input_cost_per_1m_tokens_large']:.2f}")
                print(f"  Output (≤200k): ${pricing['output_cost_per_1m_tokens_small']:.2f}")
                print(f"  Output (>200k): ${pricing['output_cost_per_1m_tokens_large']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating pricing config: {e}")
        return False

def show_pricing_info():
    """Show current pricing information"""
    project_root = os.path.dirname(os.path.dirname(__file__))
    config_path = os.path.join(project_root, 'config', 'gemini_pricing.json')
    
    if not os.path.exists(config_path):
        print("❌ Pricing config not found. Run with --update to create it.")
        return
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        print("📊 Current Gemini Pricing Configuration")
        print("=" * 50)
        print(f"Source: {config.get('source', 'N/A')}")
        print(f"Last updated: {config.get('last_updated', 'N/A')}")
        print(f"Currency: {config.get('currency', 'USD')}")
        print()
        
        for model, pricing in config.get('pricing', {}).items():
            print(f"{model}:")
            if 'input_cost_per_1m_tokens' in pricing:
                print(f"  Input: ${pricing['input_cost_per_1m_tokens']:.2f} per 1M tokens")
                print(f"  Output: ${pricing['output_cost_per_1m_tokens']:.2f} per 1M tokens")
            else:
                print(f"  Input (≤200k): ${pricing['input_cost_per_1m_tokens_small']:.2f} per 1M tokens")
                print(f"  Input (>200k): ${pricing['input_cost_per_1m_tokens_large']:.2f} per 1M tokens")
                print(f"  Output (≤200k): ${pricing['output_cost_per_1m_tokens_small']:.2f} per 1M tokens")
                print(f"  Output (>200k): ${pricing['output_cost_per_1m_tokens_large']:.2f} per 1M tokens")
            print(f"  Description: {pricing.get('description', 'N/A')}")
            print(f"  Free tier: {pricing.get('free_tier', False)}")
            print()
        
    except Exception as e:
        print(f"❌ Error reading pricing config: {e}")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--update':
        update_pricing_config()
    else:
        print("Gemini Pricing Configuration Tool")
        print("=" * 40)
        print()
        print("Options:")
        print("  python update_gemini_pricing.py --update    Update pricing config")
        print("  python update_gemini_pricing.py            Show current pricing")
        print()
        show_pricing_info()

if __name__ == "__main__":
    main()