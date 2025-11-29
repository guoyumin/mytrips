import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from backend.database.config import SessionLocal
from backend.database.models import Email, EmailContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_failed_emails():
    db = SessionLocal()
    try:
        failed_emails = db.query(Email, EmailContent).join(EmailContent).filter(
            EmailContent.trip_detection_status == 'failed'
        ).all()
        
        print(f"Found {len(failed_emails)} failed emails:")
        
        # Group by error message
        errors = {}
        for email, content in failed_emails:
            error = content.trip_detection_error or "Unknown error"
            if error not in errors:
                errors[error] = []
            errors[error].append(email.subject)
            
        for error, subjects in errors.items():
            print(f"\nError: {error}")
            print(f"Count: {len(subjects)}")
            print("Sample Subjects:")
            for subject in subjects[:5]:
                print(f"  - {subject}")
                
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_failed_emails()
