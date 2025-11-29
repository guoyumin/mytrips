import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from backend.lib.ai.providers.gemini_provider import GeminiProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_no_cost():
    print("Initializing GeminiProvider...")
    try:
        # Initialize with a dummy model version, config loading will happen but pricing is ignored
        provider = GeminiProvider('gemini-2.5-pro')
        
        # Test cost estimation
        print("\nTesting cost estimation...")
        cost = provider.estimate_cost(1000, 1000)
        print(f"Cost estimate for 1k/1k tokens: {cost}")
        
        if cost['estimated_cost_usd'] == 0.0:
            print("SUCCESS: Cost estimation is 0.0 as expected")
        else:
            print(f"FAILURE: Cost estimation returned {cost['estimated_cost_usd']}")
            
    except Exception as e:
        print(f"FAILURE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_no_cost()
