"""
Import Microservice - Handles email import from Gmail with date range support
"""
import logging
from typing import List, Dict, Set, Optional
from datetime import datetime, timedelta

from backend.lib.gmail_client import GmailClient
from backend.database.models import Email
from .base_micro_service import BaseMicroService

logger = logging.getLogger(__name__)


class ImportMicroService(BaseMicroService):
    """
    Microservice for importing emails from Gmail
    
    - Reads existing email IDs from database
    - Fetches new emails from Gmail
    - Returns results without writing to database
    """
    
    def __init__(self, gmail_client: GmailClient):
        """
        Initialize import microservice
        
        Args:
            gmail_client: Initialized Gmail client instance
        """
        super().__init__()
        self.gmail_client = gmail_client
    
    def import_emails_by_date_range(self, 
                                   start_date: datetime, 
                                   end_date: datetime,
                                   check_existing: bool = True) -> Dict:
        """
        Import emails for specified date range
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            check_existing: Whether to check for existing emails in database
            
        Returns:
            {
                'emails': List[Dict],  # New emails with headers
                'total_found': int,    # Total emails found in Gmail
                'new_count': int,      # Number of new emails
                'skipped_count': int,  # Number of existing emails skipped
                'date_range': {
                    'start': str,
                    'end': str
                }
            }
        """
        self.log_operation('import_emails_by_date_range', {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        })
        
        try:
            # Get existing IDs from database if needed
            existing_ids = set()
            if check_existing:
                existing_ids = self._get_existing_ids()
                logger.info(f"Found {len(existing_ids)} existing emails in database")
            
            # Fetch from Gmail
            logger.info(f"Searching emails from {start_date} to {end_date}")
            messages = self.gmail_client.search_emails_by_date_range(start_date, end_date)
            logger.info(f"Found {len(messages)} emails in Gmail")
            
            # Process and filter
            new_emails = []
            skipped_count = 0
            
            for msg in messages:
                email_id = msg.get('id')
                if not email_id:
                    logger.warning(f"Message without ID found: {msg}")
                    continue
                
                if email_id in existing_ids:
                    skipped_count += 1
                    logger.debug(f"Skipping existing email: {email_id}")
                    continue
                
                # Get email headers
                try:
                    headers = self.gmail_client.get_message_headers(email_id)
                    if headers:
                        headers['email_id'] = email_id
                        new_emails.append(headers)
                        logger.debug(f"Added new email: {email_id} - {headers.get('subject', 'No subject')[:50]}")
                except Exception as e:
                    logger.error(f"Failed to get headers for email {email_id}: {e}")
                    continue
            
            result = {
                'emails': new_emails,
                'total_found': len(messages),
                'new_count': len(new_emails),
                'skipped_count': skipped_count,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }
            
            logger.info(f"Import complete: {result['new_count']} new, {result['skipped_count']} skipped")
            return result
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise
    
    def import_emails_by_days(self, days: int, check_existing: bool = True) -> Dict:
        """
        Import emails from last N days (convenience method)
        
        Args:
            days: Number of days back from today
            check_existing: Whether to check for existing emails
            
        Returns:
            Same as import_emails_by_date_range
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.import_emails_by_date_range(start_date, end_date, check_existing)
    
    @BaseMicroService.with_db
    def _get_existing_ids(self, db) -> Set[str]:
        """
        Get existing email IDs from database
        
        Args:
            db: Database session (injected by decorator)
            
        Returns:
            Set of existing email IDs
        """
        existing_ids = set(row[0] for row in db.query(Email.email_id).all())
        return existing_ids
    
    @BaseMicroService.with_db
    def get_emails_in_date_range(self, db, start_date: datetime, end_date: datetime) -> List[str]:
        """
        Get email IDs already in database for a date range
        
        Useful for checking what's already imported
        
        Args:
            db: Database session (injected by decorator)
            start_date: Start date
            end_date: End date
            
        Returns:
            List of email IDs
        """
        emails = db.query(Email.email_id).filter(
            Email.timestamp >= start_date,
            Email.timestamp <= end_date
        ).all()
        
        return [email[0] for email in emails]