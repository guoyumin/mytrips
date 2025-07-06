import os
from datetime import datetime
from typing import Dict, List, Optional
import threading
import time

from lib.gmail_client import GmailClient
from lib.email_cache_db import EmailCacheDB
from lib.config_manager import config_manager

class EmailCacheService:
    """Service for managing email cache operations"""
    
    def __init__(self, credentials_path: str = None, token_path: str = None):
        # Use config manager for paths
        if credentials_path is None:
            credentials_path = config_manager.get_gmail_credentials_path()
        if token_path is None:
            token_path = config_manager.get_gmail_token_path()
        
        # Initialize email cache using database
        self.email_cache = EmailCacheDB()
        
        # Try to initialize Gmail client with error handling
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Initializing Gmail client with credentials: {credentials_path}, token: {token_path}")
            self.gmail_client = GmailClient(credentials_path, token_path)
            logger.info("Gmail client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail client: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.gmail_client = None
        
        # Initialize progress tracking
        self.import_progress = {
            'is_running': False,
            'current': 0,
            'total': 0,
            'finished': False,
            'message': '',
            'error': None,
            'new_count': 0,
            'skip_count': 0
        }
        self._stop_flag = threading.Event()
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about the email cache"""
        return self.email_cache.get_statistics()
    
    def start_import(self, days: int = 365) -> str:
        """Start importing emails from Gmail"""
        if self.import_progress.get('is_running'):
            return "Import is already running"
        
        if not self.gmail_client:
            return "Gmail client not initialized. Please check configuration."
        
        # Reset stop flag and progress
        self._stop_flag.clear()
        self.import_progress = {
            'is_running': True,
            'current': 0,
            'total': 0,
            'finished': False,
            'message': 'Starting import...',
            'error': None
        }
        
        # Start background import
        import_thread = threading.Thread(
            target=self._background_import,
            args=(days,),
            daemon=True
        )
        import_thread.start()
        
        return f"Started importing emails from the last {days} days"
    
    def get_import_progress(self) -> Dict:
        """Get current import progress"""
        progress_data = self.import_progress.copy()
        
        # Calculate progress percentage for frontend
        if progress_data['total'] > 0:
            progress_data['progress'] = (progress_data['current'] / progress_data['total']) * 100
            progress_data['processed'] = progress_data['current']
        else:
            progress_data['progress'] = 0
            progress_data['processed'] = 0
            
        return progress_data
    
    def stop_import(self) -> str:
        """Stop the ongoing import process"""
        self._stop_flag.set()
        self.import_progress['message'] = 'Stopping import...'
        return "Import stop requested"
    
    def _background_import(self, days: int):
        """Background thread for importing emails"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"Background import started for {days} days")
            
            self.import_progress.update({
                'message': 'Connecting to Gmail...',
                'current': 0,
                'total': 0
            })
            
            # Search for emails from the specified time period
            self.import_progress['message'] = f'Searching for emails from the last {days} days...'
            logger.info(f"Calling gmail_client.search_emails_by_date({days})")
            messages = self.gmail_client.search_emails_by_date(days)
            logger.info(f"Got {len(messages) if messages else 0} messages from Gmail")
            
            if not messages:
                self.import_progress.update({
                    'finished': True,
                    'message': 'No emails found for the specified date range',
                    'is_running': False
                })
                return
            
            self.import_progress.update({
                'total': len(messages),
                'message': f'Found {len(messages)} emails. Processing...'
            })
            
            # Get existing email IDs to avoid duplicates
            logger.info("Getting existing email IDs from cache...")
            existing_ids = self.email_cache.get_cached_ids()
            logger.info(f"Found {len(existing_ids)} existing email IDs in cache")
            
            # Debug: print first few IDs from both sources
            if existing_ids:
                logger.debug(f"Sample existing IDs: {list(existing_ids)[:3]}")
            if messages:
                logger.debug(f"Sample message IDs from Gmail: {[msg['id'] for msg in messages[:3]]}")
            
            # Process emails individually and add to database immediately
            new_emails = []
            new_count = 0
            skip_count = 0
            
            for i, message in enumerate(messages):
                # Check stop flag
                if self._stop_flag.is_set():
                    self.import_progress.update({
                        'finished': True,
                        'is_running': False,
                        'message': f'Import stopped by user. Processed {i} emails.'
                    })
                    return
                
                if message['id'] not in existing_ids:
                    logger.debug(f"Processing new email: {message['id']}")
                    # Get email headers
                    headers = self.gmail_client.get_message_headers(message['id'])
                    headers['email_id'] = message['id']
                    new_emails.append(headers)
                    new_count += 1
                    logger.debug(f"Added email: {headers.get('subject', 'No subject')[:50]}")
                    
                    # Add to database immediately
                    try:
                        added_count = self.email_cache.add_emails([headers])
                        logger.debug(f"Added {added_count} email to database")
                    except Exception as e:
                        logger.error(f"Error saving email to database: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                else:
                    skip_count += 1
                    logger.debug(f"Skipping existing email: {message['id']}")
                
                # Update progress
                self.import_progress.update({
                    'current': i + 1,
                    'new_count': new_count,
                    'skip_count': skip_count,
                    'message': f'Processing email {i + 1}/{len(messages)}...'
                })
            
            # Get final stats
            final_stats = self.email_cache.get_statistics()
            
            # Mark as finished
            self.import_progress.update({
                'finished': True,
                'is_running': False,
                'message': f'Import completed. Total emails processed: {self.import_progress["current"]}',
                'final_results': {
                    'new_emails': new_count,
                    'skipped_emails': skip_count,
                    'total_cached': final_stats.get('total_emails', 0),
                    'date_range': final_stats.get('date_range')
                }
            })
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            self.import_progress.update({
                'finished': True,
                'is_running': False,
                'error': str(e),
                'message': f'Import failed: {str(e)}'
            })