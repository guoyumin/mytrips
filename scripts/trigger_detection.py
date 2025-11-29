import sys
from pathlib import Path
import logging
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from backend.services.trip_detection_service import TripDetectionService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def trigger_detection():
    print("Initializing TripDetectionService...")
    service = TripDetectionService()
    
    print("Starting trip detection...")
    # This runs the background detection process
    service._background_detection()
    
    print("Trip detection cycle completed.")

if __name__ == "__main__":
    trigger_detection()
