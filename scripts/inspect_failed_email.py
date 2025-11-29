import sys
from pathlib import Path
import logging
import json

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from backend.database.config import SessionLocal
from backend.database.models import Email, EmailContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def inspect_failed_email():
    db = SessionLocal()
    try:
        # Find the failed email
        failed_email = db.query(Email, EmailContent).join(EmailContent).filter(
            EmailContent.trip_detection_status == 'failed'
        ).first()
        
        if failed_email:
            email, content = failed_email
            print(f"Subject: {email.subject}")
            print(f"Error: {content.trip_detection_error}")
            
            if content.extracted_booking_info:
                print("\nExtracted Booking Info:")
                print(json.dumps(content.extracted_booking_info, indent=2, default=str))
            else:
                print("\nNo extracted booking info found.")
        else:
            print("No failed email found with that error.")
            
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_failed_email()
