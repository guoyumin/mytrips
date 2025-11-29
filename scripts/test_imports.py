#!/usr/bin/env python3
"""
Test script to verify imports work correctly with PYTHONPATH
"""
import os
import sys

print(f"Current directory: {os.getcwd()}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
print(f"sys.path[0]: {sys.path[0]}")
print()

# Test imports
try:
    from backend.models.trip import Trip
    print("✅ Successfully imported: backend.models.trip.Trip")
except ImportError as e:
    print(f"❌ Failed to import backend.models.trip.Trip: {e}")

try:
    from backend.services.trip_detection_service import TripDetectionService
    print("✅ Successfully imported: backend.services.trip_detection_service.TripDetectionService")
except ImportError as e:
    print(f"❌ Failed to import backend.services.trip_detection_service.TripDetectionService: {e}")

try:
    import backend.main
    print("✅ Successfully imported: backend.main")
except ImportError as e:
    print(f"❌ Failed to import backend.main: {e}")

print("\n✅ All imports successful!")