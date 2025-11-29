import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from backend.lib.ai.ai_provider_with_fallback import AIProviderWithFallback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_config():
    print("Initializing AIProviderWithFallback...")
    try:
        provider = AIProviderWithFallback([('gemini', 'powerful')])
        
        info = provider.get_model_info()
        print(f"Model Info: {info}")
        
        if 'gemini-2.5-pro' in info['model_name']:
            print("SUCCESS: Correct model loaded (gemini-2.5-pro)")
        else:
            print(f"FAILURE: Incorrect model loaded: {info['model_name']}")
            
        # Test cost estimation
        print("\nTesting cost estimation...")
        cost = provider.estimate_cost(1000, 1000)
        print(f"Cost estimate for 1k/1k tokens: {cost}")
        
        if cost['estimated_cost_usd'] > 0:
            print("SUCCESS: Cost estimation working")
        else:
            print("WARNING: Cost estimation returned 0 (might be expected if using free tier defaults, but we set defaults)")
            
    except Exception as e:
        print(f"FAILURE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_config()
