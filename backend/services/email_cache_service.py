import csv
import os
from datetime import datetime
from typing import Dict, List, Optional, Set
from email.utils import parsedate_to_datetime
import threading
import time

from services.gmail_service import GmailService

class EmailCacheService:
    """Service for managing email cache operations"""
    
    def __init__(self, cache_file: str = None):
        if cache_file is None:
            # Use data directory for cache file
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            cache_file = os.path.join(project_root, 'data', 'email_cache.csv')
        self.cache_file = cache_file
        self.csv_headers = ['email_id', 'subject', 'from', 'date', 'timestamp', 'is_classified', 'classification']
        self.import_progress = {}
        self._stop_flag = threading.Event()
        
    def get_cached_email_ids(self) -> Set[str]:
        """Get set of email IDs already in cache"""
        cached_ids = set()
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cached_ids.add(row['email_id'])
        return cached_ids
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about cached emails"""
        if not os.path.exists(self.cache_file):
            return {
                'total_emails': 0,
                'classified_emails': 0,
                'date_range': None
            }
            
        total = 0
        classified = 0
        dates = []
        
        with open(self.cache_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                if row.get('is_classified', 'false').lower() == 'true':
                    classified += 1
                    
                # Parse date for range
                try:
                    date_str = row.get('date', '')
                    if date_str:
                        email_date = parsedate_to_datetime(date_str)
                        # Convert to naive datetime if it has timezone info
                        if email_date.tzinfo is not None:
                            email_date = email_date.replace(tzinfo=None)
                        dates.append(email_date)
                except Exception as e:
                    # Skip invalid dates
                    pass
        
        date_range = None
        if dates:
            dates.sort()
            date_range = {
                'oldest': dates[0].strftime('%Y-%m-%d'),
                'newest': dates[-1].strftime('%Y-%m-%d')
            }
            
        return {
            'total_emails': total,
            'classified_emails': classified,
            'date_range': date_range
        }
    
    def start_import(self, days: int = 365) -> str:
        """Start email import process in background"""
        if hasattr(self, '_import_thread') and self._import_thread.is_alive():
            raise Exception("Import already in progress")
            
        # Reset stop flag
        self._stop_flag.clear()
        
        # Initialize progress tracking
        self.import_progress = {
            'total': 0,
            'processed': 0,
            'new_count': 0,
            'skip_count': 0,
            'finished': False,
            'error': None,
            'start_time': datetime.now(),
            'final_results': None
        }
        
        # Start import thread
        self._import_thread = threading.Thread(
            target=self._background_import,
            args=(days,),
            daemon=True
        )
        self._import_thread.start()
        
        return "Import started"
    
    def stop_import(self) -> str:
        """Stop ongoing import process"""
        self._stop_flag.set()
        return "Stop signal sent"
    
    def get_import_progress(self) -> Dict:
        """Get current import progress"""
        progress = self.import_progress.copy()
        
        # Calculate percentage
        if progress.get('total', 0) > 0:
            progress['progress'] = round(
                (progress.get('processed', 0) / progress['total']) * 100, 1
            )
        else:
            progress['progress'] = 0
            
        return progress
    
    def _background_import(self, days: int):
        """Background import process"""
        try:
            gmail_service = GmailService()
            cached_ids = self.get_cached_email_ids()
            
            # Search for emails
            query = f'newer_than:{days}d'
            all_emails = self._fetch_all_emails(gmail_service, query)
            
            self.import_progress['total'] = len(all_emails)
            
            # Ensure CSV file exists
            self._ensure_csv_exists()
            
            # Process emails
            new_count, skip_count, date_range = self._process_emails(
                gmail_service, all_emails, cached_ids
            )
            
            # Store final results
            total_cached = len(cached_ids) + new_count
            self.import_progress['final_results'] = {
                'new_emails': new_count,
                'skipped_emails': skip_count,
                'total_cached': total_cached,
                'date_range': date_range
            }
            
        except Exception as e:
            self.import_progress['error'] = str(e)
        finally:
            self.import_progress['finished'] = True
    
    def _fetch_all_emails(self, gmail_service: GmailService, query: str) -> List[Dict]:
        """Fetch all emails matching query with pagination"""
        all_emails = []
        page_token = None
        
        while True:
            if self._stop_flag.is_set():
                break
                
            try:
                if page_token:
                    results = gmail_service.service.users().messages().list(
                        userId='me',
                        q=query,
                        pageToken=page_token,
                        maxResults=500
                    ).execute()
                else:
                    results = gmail_service.service.users().messages().list(
                        userId='me',
                        q=query,
                        maxResults=500
                    ).execute()
                
                messages = results.get('messages', [])
                all_emails.extend(messages)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as e:
                print(f"Error fetching emails: {e}")
                break
        
        return all_emails
    
    def _ensure_csv_exists(self):
        """Ensure CSV file exists with proper headers"""
        if not os.path.exists(self.cache_file):
            with open(self.cache_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.csv_headers)
                writer.writeheader()
    
    def _process_emails(self, gmail_service: GmailService, all_emails: List[Dict], 
                       cached_ids: Set[str]) -> tuple:
        """Process and cache emails"""
        new_count = 0
        skip_count = 0
        dates = []
        
        with open(self.cache_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.csv_headers)
            
            for i, email in enumerate(all_emails):
                if self._stop_flag.is_set():
                    break
                
                email_id = email['id']
                self.import_progress['processed'] = i + 1
                
                # Skip if already cached
                if email_id in cached_ids:
                    skip_count += 1
                    self.import_progress['skip_count'] = skip_count
                    continue
                
                try:
                    # Fetch email details
                    email_data = gmail_service.get_email(email_id)
                    
                    # Parse date for range tracking
                    date_str = email_data.get('date', '')
                    try:
                        if date_str:
                            email_date = parsedate_to_datetime(date_str)
                            # Convert to naive datetime if it has timezone info
                            if email_date.tzinfo is not None:
                                email_date = email_date.replace(tzinfo=None)
                            dates.append(email_date)
                    except Exception as e:
                        # Skip invalid dates
                        pass
                    
                    # Write to CSV
                    writer.writerow({
                        'email_id': email_id,
                        'subject': email_data.get('subject', ''),
                        'from': email_data.get('from', ''),
                        'date': date_str,
                        'timestamp': datetime.now().isoformat(),
                        'is_classified': 'false',
                        'classification': ''
                    })
                    
                    new_count += 1
                    self.import_progress['new_count'] = new_count
                    
                    # Small delay to prevent rate limiting
                    time.sleep(0.01)
                    
                except Exception as e:
                    print(f"Error processing email {email_id}: {e}")
                    continue
        
        # Calculate date range
        date_range = None
        if dates:
            dates.sort()
            date_range = {
                'oldest': dates[0].strftime('%Y-%m-%d'),
                'newest': dates[-1].strftime('%Y-%m-%d')
            }
        
        return new_count, skip_count, date_range