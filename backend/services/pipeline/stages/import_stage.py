"""
Import Stage for Email Pipeline
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from email.utils import parsedate_to_datetime

from backend.services.pipeline.base_stage import BasePipelineStage
from backend.lib.gmail_client import GmailClient
from backend.lib.config_manager import config_manager
from backend.database.models import Email

logger = logging.getLogger(__name__)


class ImportStage(BasePipelineStage):
    """Stage for importing emails from Gmail"""
    
    def __init__(self, batch_size: int = 100):
        super().__init__("Import", batch_size)
        
        # Initialize Gmail client
        credentials_path = config_manager.get_gmail_credentials_path()
        token_path = config_manager.get_gmail_token_path()
        self.gmail_client = GmailClient(credentials_path, token_path)
        
        # Track existing emails
        self.existing_ids = set()
        self.date_range = None
    
    def set_date_range(self, date_range: Dict):
        """Set the date range for import"""
        self.date_range = date_range
    
    def check_pending_work(self) -> Optional[List[str]]:
        """Import stage doesn't have pending work - it always starts fresh"""
        return None
    
    def process_batch(self, batch_data: Dict) -> Dict:
        """Process batch is not used for import - we use run_import instead"""
        pass
    
    def run_import(self, date_range: Dict, output_queue):
        """
        Run the import process
        
        Args:
            date_range: Dict with 'start_date' and 'end_date'
            output_queue: Queue to send imported emails for classification
        """
        try:
            self.start()
            self.date_range = date_range
            
            # Convert string dates to datetime objects
            start_date = datetime.strptime(date_range['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(date_range['end_date'], '%Y-%m-%d')
            
            logger.info(f"Starting import for date range: {start_date} to {end_date}")
            
            # Get existing email IDs from database
            self._load_existing_emails()
            
            # Import emails page by page
            page_token = None
            total_imported = 0
            total_skipped = 0
            batch_number = 0
            
            while not self.is_stopped():
                # Get next page of emails
                logger.info(f"Fetching page {batch_number + 1} of emails...")
                logger.debug(f"Import stage - is_stopped: {self.is_stopped()}")
                page_result = self.gmail_client.search_emails_by_date_range_paginated(
                    start_date=start_date,
                    end_date=end_date,
                    page_token=page_token,
                    max_results=self.batch_size
                )
                
                messages = page_result.get('messages', [])
                if not messages:
                    logger.info("No more emails to import")
                    break
                
                logger.info(f"Processing batch {batch_number + 1} with {len(messages)} emails")
                
                # Process this batch
                new_emails = []
                batch_skipped = 0
                
                for msg in messages:
                    email_id = msg.get('id')
                    if email_id in self.existing_ids:
                        batch_skipped += 1
                        continue
                    
                    # Get email headers
                    try:
                        headers = self.gmail_client.get_message_headers(email_id)
                        if headers:
                            headers['email_id'] = email_id
                            new_emails.append(headers)
                    except Exception as e:
                        logger.error(f"Failed to get headers for email {email_id}: {e}")
                
                # Save new emails to database
                if new_emails:
                    saved_count = self._save_emails_batch(new_emails)
                    total_imported += saved_count
                    
                    # Send to classification queue
                    email_ids = [email['email_id'] for email in new_emails]
                    output_queue.put({
                        'email_ids': email_ids,
                        'batch_size': len(email_ids)
                    })
                    
                    logger.info(f"Saved {saved_count} emails and sent for classification")
                
                total_skipped += batch_skipped
                batch_number += 1
                
                # Update progress
                estimated_total = page_result.get('resultSizeEstimate', 0)
                self.update_progress(
                    processed=total_imported,
                    total=estimated_total,
                    failed=total_skipped
                )
                
                # Check for next page
                page_token = page_result.get('nextPageToken')
                if not page_token:
                    logger.info("No more pages to import")
                    break
            
            # Signal end of import
            output_queue.put(None)
            
            self.complete()
            logger.info(f"Import completed. Total imported: {total_imported}, skipped: {total_skipped}")
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            self.fail(str(e))
            raise
    
    def _load_existing_emails(self):
        """Load existing email IDs from database"""
        db = self.get_db_session()
        try:
            existing_ids = db.query(Email.email_id).all()
            self.existing_ids = set(row[0] for row in existing_ids)
            logger.info(f"Found {len(self.existing_ids)} existing emails in database")
        finally:
            db.close()
    
    def _save_emails_batch(self, emails: List[Dict]) -> int:
        """Save a batch of emails to database"""
        db = self.get_db_session()
        saved_count = 0
        
        try:
            for email_data in emails:
                try:
                    # Parse date
                    date_str = email_data.get('date', '')
                    try:
                        email_date = parsedate_to_datetime(date_str)
                    except:
                        email_date = datetime.now()
                    
                    # Create email record
                    email = Email(
                        email_id=email_data['email_id'],
                        subject=email_data.get('subject', 'No Subject'),
                        sender=email_data.get('from', 'Unknown'),
                        date=date_str,
                        timestamp=email_date
                    )
                    
                    db.add(email)
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to save email {email_data.get('email_id')}: {e}")
            
            db.commit()
            logger.info(f"Saved {saved_count} emails to database")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save email batch: {e}")
        finally:
            db.close()
        
        return saved_count