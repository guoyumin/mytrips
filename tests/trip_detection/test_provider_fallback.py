#!/usr/bin/env python
"""Test the provider fallback logic in trip_detection_service"""
import sys
sys.path.insert(0, '/Users/guoyumin/Workspace/Mytrips/backend')

from services.trip_detection_service import TripDetectionService

def test_provider_fallback():
    """Test that the service starts with gemini-fast and can switch providers"""
    
    print("Testing provider fallback logic...")
    
    # Create service instance
    service = TripDetectionService()
    
    # Check initial provider
    initial_provider = service.ai_provider.get_model_info()
    print(f"\nInitial provider: {initial_provider['provider']} - {initial_provider['model_name']}")
    
    # Test provider switching
    print("\nTesting provider switching...")
    
    # First switch (should go to openai-fast)
    if service._switch_to_next_provider():
        provider_info = service.ai_provider.get_model_info()
        print(f"After 1st switch: {provider_info['provider']} - {provider_info['model_name']}")
    
    # Second switch (should go to claude-fast)
    if service._switch_to_next_provider():
        provider_info = service.ai_provider.get_model_info()
        print(f"After 2nd switch: {provider_info['provider']} - {provider_info['model_name']}")
    
    # Third switch (should fail - all providers exhausted)
    if not service._switch_to_next_provider():
        print("After 3rd switch: All providers exhausted (as expected)")
    
    print("\nProvider fallback test completed!")

if __name__ == "__main__":
    test_provider_fallback()