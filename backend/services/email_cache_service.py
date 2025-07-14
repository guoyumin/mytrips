import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
import time
import logging

from backend.lib.gmail_client import GmailClient
from backend.lib.email_cache_db import EmailCacheDB
from backend.lib.config_manager import config_manager
from backend.services.micro.import_micro_service import ImportMicroService
from backend.database.config import SessionLocal
from backend.database.models import Email

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
            
            # Initialize ImportMicroService
            self.import_micro = ImportMicroService(self.gmail_client)
            logger.info("ImportMicroService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail client: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.gmail_client = None
            self.import_micro = None
        
        # Initialize progress tracking with thread safety
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
        self._import_thread = None
        self._lock = threading.Lock()  # Add thread lock for safety
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about the email cache"""
        return self.email_cache.get_statistics()
    
    def start_import(self, days: int = 365) -> str:
        """Start importing emails from Gmail (legacy method using thread)"""
        # Convert days to date range and call new method
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.start_import_date_range(start_date, end_date)
    
    def start_import_date_range(self, start_date: datetime, end_date: datetime) -> str:
        """Start importing emails from Gmail for a specific date range"""
        with self._lock:
            if self.import_progress.get('is_running'):
                return "Import is already running"
            
            # Double-check thread status
            if self._import_thread and self._import_thread.is_alive():
                return "Import thread already running"
            
            if not self.import_micro:
                return "Import service not initialized. Please check configuration."
            
            # Reset stop flag and progress
            self._stop_flag.clear()
            self.import_progress = {
                'is_running': True,
                'current': 0,
                'total': 0,
                'finished': False,
                'message': 'Starting import...',
                'error': None,
                'new_count': 0,
                'skip_count': 0,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
            
            # Start background import
            self._import_thread = threading.Thread(
                target=self._background_import_date_range,
                args=(start_date, end_date),
                daemon=True
            )
            self._import_thread.start()
            
            return f"Started importing emails from {start_date.date()} to {end_date.date()}"
    
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
        with self._lock:
            self._stop_flag.set()
            if self.import_progress.get('is_running'):
                self.import_progress['is_running'] = False
                self.import_progress['finished'] = True
                self.import_progress['message'] = 'Import stopped by user'
        return "Import stop requested"
    
    def import_date_range_sync(self, start_date: datetime, end_date: datetime) -> Dict:
        """Synchronous version of import for pipeline use"""
        logger = logging.getLogger(__name__)
        
        if not self.import_micro:
            raise Exception("Import service not initialized")
        
        # Use microservice to import
        import_result = self.import_micro.import_emails_by_date_range(
            start_date, end_date
        )
        
        # Save to database
        if import_result['emails']:
            saved_count = self._save_emails_to_database(import_result['emails'])
            import_result['saved_count'] = saved_count
        
        return import_result
    
    def _save_emails_to_database(self, emails: List[Dict]) -> int:
        """Save emails to database and return count saved"""
        db = SessionLocal()
        saved_count = 0
        
        try:
            for email_data in emails:
                # Check if email already exists
                existing = db.query(Email).filter_by(
                    email_id=email_data['email_id']
                ).first()
                
                if not existing:
                    # Map fields correctly (from -> sender)
                    email_fields = {
                        'email_id': email_data['email_id'],
                        'subject': email_data.get('subject'),
                        'sender': email_data.get('from'),  # Map 'from' to 'sender'
                        'date': email_data.get('date'),
                        'classification': 'unclassified'
                    }
                    
                    # Parse timestamp if date is available
                    if email_fields['date']:
                        try:
                            from email.utils import parsedate_to_datetime
                            email_fields['timestamp'] = parsedate_to_datetime(email_fields['date'])
                        except Exception as e:
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Failed to parse date for email {email_data['email_id']}: {e}")
                    
                    email = Email(**email_fields)
                    db.add(email)
                    saved_count += 1
            
            db.commit()
            return saved_count
            
        except Exception as e:
            db.rollback()
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to save emails: {e}")
            raise
        finally:
            db.close()
    
    def _background_import_date_range(self, start_date: datetime, end_date: datetime):
        """Background thread for importing emails with date range"""
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"Background import started for date range: {start_date} to {end_date}")
            
            self.import_progress.update({
                'message': 'Connecting to Gmail...',
                'current': 0,
                'total': 0
            })
            
            # Use microservice to import
            self.import_progress['message'] = f'Searching for emails from {start_date.date()} to {end_date.date()}...'
            
            import_result = self.import_micro.import_emails_by_date_range(
                start_date, end_date
            )
            
            total_found = import_result['total_found']
            new_emails = import_result['emails']
            
            if not new_emails:
                with self._lock:
                    self.import_progress.update({
                        'finished': True,
                        'message': f'No new emails found. {import_result["skipped_count"]} already imported.',
                        'is_running': False,
                        'total': total_found,
                        'skip_count': import_result['skipped_count']
                    })
                return
            
            self.import_progress.update({
                'total': total_found,
                'message': f'Found {len(new_emails)} new emails to import. Processing...'
            })
            
            # Save emails to database in batches
            batch_size = 50
            saved_count = 0
            
            for i in range(0, len(new_emails), batch_size):
                # Check stop flag
                if self._stop_flag.is_set():
                    with self._lock:
                        self.import_progress.update({
                            'finished': True,
                            'is_running': False,
                            'message': f'Import stopped by user. Saved {saved_count} emails.'
                        })
                    return
                
                batch = new_emails[i:i + batch_size]
                batch_saved = self._save_emails_to_database(batch)
                saved_count += batch_saved
                
                # Update progress
                self.import_progress.update({
                    'current': min(i + batch_size, len(new_emails)),
                    'new_count': saved_count,
                    'skip_count': import_result['skipped_count'],
                    'message': f'Saving emails... {saved_count}/{len(new_emails)}'
                })
            
            # Get final stats
            final_stats = self.email_cache.get_statistics()
            
            # Mark as finished
            with self._lock:
                self.import_progress.update({
                    'finished': True,
                    'is_running': False,
                    'message': f'Import completed. Imported {saved_count} new emails.',
                    'new_count': saved_count,
                    'skip_count': import_result['skipped_count'],
                    'final_results': {
                        'total_in_cache': final_stats['total_emails'],
                        'new_emails_added': saved_count,
                        'skipped_existing': import_result['skipped_count']
                    }
                })
            
            logger.info(f"Import finished: {saved_count} new, {import_result['skipped_count']} skipped")
            
        except Exception as e:
            logger.error(f"Error during background import: {e}")
            import traceback
            logger.error(traceback.format_exc())
            with self._lock:
                self.import_progress.update({
                    'finished': True,
                    'is_running': False,
                    'error': str(e),
                    'message': f'Import failed: {str(e)}'
                })
    
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
                with self._lock:
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
                    with self._lock:
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
            with self._lock:
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
            
            with self._lock:
                self.import_progress.update({
                    'finished': True,
                    'is_running': False,
                    'error': str(e),
                    'message': f'Import failed: {str(e)}'
                })
    
    def reset_all_emails(self) -> Dict:
        """清除所有缓存的邮件数据"""
        logger = logging.getLogger(__name__)
        
        try:
            # 确保没有正在运行的导入任务
            if self.import_progress.get('is_running'):
                return {
                    'success': False,
                    'message': '邮件导入正在进行中，请先停止导入'
                }
            
            # 清除数据库中的所有邮件
            deleted_count = self.email_cache.clear_all()
            
            # 重置导入进度
            with self._lock:
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
            
            logger.info(f"成功清除 {deleted_count} 封邮件")
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'message': f'成功清除 {deleted_count} 封邮件'
            }
            
        except Exception as e:
            logger.error(f"清除邮件失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'清除邮件失败: {str(e)}'
            }