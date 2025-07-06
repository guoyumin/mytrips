#!/usr/bin/env python3
"""Test batch classification with actual email data to reproduce the issue"""

import os
import sys
import csv
import traceback
from datetime import datetime
sys.path.append('/Users/guoyumin/Workspace/Mytrips/backend')

from services.gemini_service import GeminiService

def test_batch_classification():
    """Test batch classification with actual email data"""
    
    print("🔍 Testing Batch Classification with Real Email Data")
    print("="*60)
    
    # Initialize Gemini service
    try:
        gemini_service = GeminiService()
        print("✅ Gemini Service initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Gemini Service: {e}")
        return False
    
    # Load actual email data
    cache_file = '/Users/guoyumin/Workspace/Mytrips/data/email_cache.csv'
    if not os.path.exists(cache_file):
        print(f"❌ Cache file not found: {cache_file}")
        return False
    
    # Load different batch sizes to test
    batch_sizes = [10, 20, 50]
    
    for batch_size in batch_sizes:
        print(f"\n🧪 Testing batch size: {batch_size}")
        print("-" * 40)
        
        # Load emails
        emails = []
        with open(cache_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= batch_size:
                    break
                emails.append(row)
        
        print(f"Loaded {len(emails)} emails")
        
        # Test classification
        try:
            print("Calling classify_emails_batch...")
            results = gemini_service.classify_emails_batch(emails)
            
            # Check results
            failed_count = sum(1 for r in results if r.get('classification') == 'classification_failed')
            success_count = len(results) - failed_count
            
            print(f"✅ Batch classification completed")
            print(f"   Total: {len(results)}")
            print(f"   Success: {success_count}")
            print(f"   Failed: {failed_count}")
            
            if failed_count > 0:
                print(f"❌ {failed_count} classifications failed!")
                # Print some examples of failed classifications
                for i, result in enumerate(results[:3]):
                    if result.get('classification') == 'classification_failed':
                        print(f"   Failed example {i+1}: {result.get('subject', 'N/A')[:50]}...")
            else:
                print("✅ All classifications succeeded")
                
        except Exception as e:
            print(f"❌ Batch classification failed: {e}")
            traceback.print_exc()
            
            # Check if it's a rate limit or internal error
            if "500 An internal error has occurred" in str(e):
                print("🔍 This is the same 500 error we saw in the logs!")
                print("   This suggests the issue is with batch size or rate limiting")
            elif "quota" in str(e).lower() or "rate" in str(e).lower():
                print("🔍 This appears to be a rate limiting issue")
            else:
                print(f"🔍 Unexpected error type: {type(e).__name__}")
    
    # Test with different approaches
    print(f"\n🧪 Testing with delays between calls")
    print("-" * 40)
    
    # Test smaller batches with delays
    try:
        import time
        
        small_batch_size = 20
        emails = []
        with open(cache_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= small_batch_size:
                    break
                emails.append(row)
        
        print(f"Testing {small_batch_size} emails with 2-second delay...")
        time.sleep(2)  # Wait 2 seconds before call
        
        results = gemini_service.classify_emails_batch(emails)
        failed_count = sum(1 for r in results if r.get('classification') == 'classification_failed')
        
        print(f"✅ With delay - Success: {len(results) - failed_count}, Failed: {failed_count}")
        
    except Exception as e:
        print(f"❌ Delayed batch classification failed: {e}")
    
    # Test API quota status
    print(f"\n🧪 Testing API quota status")
    print("-" * 40)
    
    try:
        # Make a simple API call to check quota
        simple_response = gemini_service.model.generate_content("Hello, respond with 'OK'")
        print(f"✅ Simple API call successful: {simple_response.text}")
    except Exception as e:
        print(f"❌ Simple API call failed: {e}")
        if "quota" in str(e).lower():
            print("🔍 This is likely a quota/rate limit issue")
        
    print("\n🎉 Batch classification test completed!")
    return True

if __name__ == "__main__":
    success = test_batch_classification()
    sys.exit(0 if success else 1)