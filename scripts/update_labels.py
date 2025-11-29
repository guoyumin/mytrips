import sys
from pathlib import Path
import json
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from backend.lib.gmail_client import GmailClient
from backend.lib.config_manager import config_manager
from backend.database.config import SessionLocal
from backend.database.models import Email

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_recent_labels(limit=10):
    db = SessionLocal()
    try:
        # Get recent emails with no labels
        emails = db.query(Email).filter(Email.labels == None).order_by(Email.id.desc()).limit(limit).all()
        
        if not emails:
            print("No emails found with missing labels.")
            return

        print(f"Found {len(emails)} emails to update...")
        
        # Initialize Gmail client
        credentials_path = config_manager.get_gmail_credentials_path()
        token_path = config_manager.get_gmail_token_path()
        client = GmailClient(credentials_path, token_path)
        
        updated_count = 0
        
        for email in emails:
            try:
                print(f"Updating email {email.email_id}...")
                headers = client.get_message_headers(email.email_id)
                
                label_names = headers.get('label_names', [])
                if label_names:
                    labels_json = json.dumps(label_names)
                    email.labels = labels_json
                    updated_count += 1
                    print(f"  -> Set labels: {labels_json}")
                else:
                    print(f"  -> No labels found in Gmail")
                    
            except Exception as e:
                print(f"  -> Failed: {e}")
                
        db.commit()
        print(f"\nSuccessfully updated {updated_count} emails.")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_recent_labels()
