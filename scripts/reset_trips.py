import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from backend.services.trip_detection_service import TripDetectionService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_trips():
    print("Initializing TripDetectionService...")
    service = TripDetectionService()
    
    print("Resetting trip detection status and clearing trips...")
    result = service.reset_trip_detection_status()
    
    print("\nResult:")
    print(result)

if __name__ == "__main__":
    reset_trips()
