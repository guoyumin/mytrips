#!/usr/bin/env python3
"""
Test the new API endpoints
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api"

def test_api_endpoints():
    print("\n=== Testing New API Endpoints ===\n")
    
    # Test 1: Import with date range
    print("1. Testing date range import...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    
    response = requests.post(f"{BASE_URL}/emails/import/date-range", json={
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "process_immediately": False
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Import successful: {data['import_result']['new_count']} new emails")
    else:
        print(f"   ✗ Import failed: {response.status_code} - {response.text}")
    
    # Test 2: Process classification
    print("\n2. Testing classification endpoint...")
    response = requests.post(f"{BASE_URL}/emails/process/classify", json={
        "limit": 10,
        "auto_continue": False
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Classification successful: {data['message']}")
    else:
        print(f"   ✗ Classification failed: {response.status_code} - {response.text}")
    
    # Test 3: Process content extraction
    print("\n3. Testing content extraction endpoint...")
    response = requests.post(f"{BASE_URL}/emails/process/content-extraction", json={
        "limit": 5,
        "auto_continue": False
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Content extraction successful: {data['message']}")
    else:
        print(f"   ✗ Content extraction failed: {response.status_code} - {response.text}")
    
    # Test 4: Process booking extraction
    print("\n4. Testing booking extraction endpoint...")
    response = requests.post(f"{BASE_URL}/emails/process/booking-extraction", json={
        "limit": 5
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Booking extraction successful: {data['message']}")
    else:
        print(f"   ✗ Booking extraction failed: {response.status_code} - {response.text}")
    
    # Test 5: Get detailed stats
    print("\n5. Testing stats endpoint...")
    response = requests.get(f"{BASE_URL}/emails/stats/detailed")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Stats retrieved successfully:")
        print(f"     Total emails: {data['total_emails']}")
        print(f"     Travel emails: {data['travel_summary']['total_travel_emails']}")
        print(f"     Content extracted: {data['content_extraction']['extracted']}")
        print(f"     Bookings extracted: {data['booking_extraction']['completed']}")
    else:
        print(f"   ✗ Stats failed: {response.status_code} - {response.text}")
    
    print("\n=== API Testing Complete ===\n")

if __name__ == "__main__":
    test_api_endpoints()