import sys
import os
from pathlib import Path
import json
import logging
import time
from typing import List, Dict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from backend.lib.gmail_client import GmailClient
from backend.lib.config_manager import config_manager
from backend.database.config import SessionLocal
from backend.database.models import Email

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backfill_labels.log')
    ]
)
logger = logging.getLogger(__name__)

def backfill_labels(batch_size: int = 50):
    """
    Backfill labels for emails that don't have them.
    Uses batch processing for efficiency.
    """
    db = SessionLocal()
    try:
        # Initialize Gmail client
        credentials_path = config_manager.get_gmail_credentials_path()
        token_path = config_manager.get_gmail_token_path()
        client = GmailClient(credentials_path, token_path)
        
        # Count total emails to process
        total_count = db.query(Email).filter(Email.labels == None).count()
        logger.info(f"Found {total_count} emails to update")
        
        processed_count = 0
        updated_count = 0
        
        while True:
            # Get a batch of emails with missing labels
            emails = db.query(Email).filter(Email.labels == None).limit(batch_size).all()
            
            if not emails:
                break
            
            email_ids = [email.email_id for email in emails]
            email_map = {email.email_id: email for email in emails}
            
            logger.info(f"Processing batch of {len(email_ids)} emails ({processed_count}/{total_count})...")
            
            try:
                # Use batch_get_headers for efficiency
                # Note: batch_get_headers returns a list of dicts with 'email_id' and 'label_names'
                headers_list = client.batch_get_headers(email_ids, batch_size=batch_size)
                
                # Create a map of results
                results_map = {h['email_id']: h.get('label_names', []) for h in headers_list}
                
                # Update database records
                for email_id in email_ids:
                    email = email_map[email_id]
                    
                    if email_id in results_map:
                        label_names = results_map[email_id]
                        # Always set labels, even if empty list, to mark as processed (empty list vs None)
                        # But wait, if we set to "[]", it's not None anymore.
                        labels_json = json.dumps(label_names)
                        email.labels = labels_json
                        updated_count += 1
                    else:
                        # If we couldn't fetch it (e.g. deleted), maybe mark as processed with empty labels?
                        # Or leave as None? If we leave as None, we'll pick it up again.
                        # Let's set to empty list to avoid infinite loop
                        logger.warning(f"Could not fetch headers for {email_id}, setting empty labels")
                        email.labels = "[]"
                
                db.commit()
                processed_count += len(emails)
                
                # Rate limiting to be nice to Gmail API
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                db.rollback()
                # If batch fails, we might get stuck in loop. 
                # For this script, let's just break or sleep longer.
                time.sleep(5)
        
        logger.info(f"Backfill completed. Updated {updated_count} emails.")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # You can adjust batch size if needed
    backfill_labels(batch_size=50)
