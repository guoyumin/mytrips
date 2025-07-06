import csv
import os
from typing import List, Dict, Optional
from datetime import datetime
import threading
import time

from services.gemini_service import GeminiService

class EmailClassificationService:
    """Service for classifying emails using Gemini AI"""
    
    def __init__(self, cache_file: str = None, test_file: str = None):
        # Data directory paths
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        data_dir = os.path.join(project_root, 'data')
        
        if cache_file is None:
            cache_file = os.path.join(data_dir, 'email_cache.csv')
        if test_file is None:
            test_file = os.path.join(data_dir, 'email_classification_test.csv')
            
        self.cache_file = cache_file
        self.test_file = test_file
        self.csv_headers = ['email_id', 'subject', 'from', 'date', 'timestamp', 'is_classified', 'classification']
        
        # Classification progress tracking
        self.classification_progress = {}
        self._stop_flag = threading.Event()
        self._classification_thread = None
        
        # Initialize Gemini service
        try:
            self.gemini_service = GeminiService()
        except Exception as e:
            print(f"Warning: Gemini service not available: {e}")
            self.gemini_service = None
    
    def start_test_classification(self, limit: int = 1000) -> Dict:
        """Start test classification of emails in background"""
        if self._classification_thread and self._classification_thread.is_alive():
            raise Exception("Classification already in progress")
        
        if not self.gemini_service:
            raise Exception("Gemini service not available. Please configure Gemini API key.")
        
        # Reset stop flag
        self._stop_flag.clear()
        
        # Initialize progress tracking
        self.classification_progress = {
            'total': 0,
            'processed': 0,
            'classified_count': 0,
            'skipped_count': 0,
            'current_batch': 0,
            'total_batches': 0,
            'batch_size': 20,
            'finished': False,
            'error': None,
            'start_time': datetime.now(),
            'estimated_cost': None
        }
        
        # Start classification thread
        self._classification_thread = threading.Thread(
            target=self._background_classification,
            args=(limit,),
            daemon=True
        )
        self._classification_thread.start()
        
        limit_msg = f"up to {limit} emails" if limit else "all unclassified emails"
        return {"started": True, "message": f"Starting test classification of {limit_msg}"}
    
    def stop_classification(self) -> str:
        """Stop ongoing classification process"""
        self._stop_flag.set()
        return "Stop signal sent"
    
    def get_classification_progress(self) -> Dict:
        """Get current classification progress"""
        progress = self.classification_progress.copy()
        
        # Calculate percentage
        if progress.get('total', 0) > 0:
            progress['progress'] = round(
                (progress.get('processed', 0) / progress['total']) * 100, 1
            )
        else:
            progress['progress'] = 0
        
        return progress
    
    def _background_classification(self, limit: int):
        """Background classification process"""
        try:
            # Load unclassified emails
            unclassified_emails = self._load_unclassified_emails(limit)
            
            if not unclassified_emails:
                self.classification_progress['error'] = "No unclassified emails found"
                return
            
            self.classification_progress['total'] = len(unclassified_emails)
            
            # Calculate batches
            batch_size = self.classification_progress['batch_size']
            total_batches = (len(unclassified_emails) + batch_size - 1) // batch_size
            self.classification_progress['total_batches'] = total_batches
            
            # Estimate cost
            cost_estimate = self.gemini_service.estimate_token_cost(len(unclassified_emails))
            self.classification_progress['estimated_cost'] = cost_estimate
            
            print(f"Starting classification of {len(unclassified_emails)} emails")
            print(f"Processing in {total_batches} batches of {batch_size} emails each")
            print(f"Estimated cost: ${cost_estimate['estimated_cost_usd']:.6f}")
            
            # Process emails in batches to optimize API calls
            classified_results = []
            save_frequency = 10  # Save every 10 batches (200 emails)
            
            for i in range(0, len(unclassified_emails), batch_size):
                if self._stop_flag.is_set():
                    print("Classification stopped by user")
                    break
                
                current_batch = (i // batch_size) + 1
                batch = unclassified_emails[i:i + batch_size]
                
                # Update current batch number
                self.classification_progress['current_batch'] = current_batch
                
                try:
                    print(f"Processing batch {current_batch}/{total_batches} ({len(batch)} emails)...")
                    
                    # Classify batch
                    batch_results = self.gemini_service.classify_emails_batch(batch)
                    classified_results.extend(batch_results)
                    
                    # Update progress
                    self.classification_progress['processed'] = min(i + batch_size, len(unclassified_emails))
                    self.classification_progress['classified_count'] = len(classified_results)
                    
                    print(f"Completed batch {current_batch}/{total_batches}, processed {self.classification_progress['processed']}/{len(unclassified_emails)} emails")
                    
                    # Save results incrementally every 5 batches
                    if current_batch % save_frequency == 0:
                        print(f"Saving incremental results after batch {current_batch}...")
                        self._save_incremental_results(classified_results)
                    
                    # Small delay to respect API rate limits
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"Error classifying batch {i//batch_size + 1}: {e}")
                    # Add default classifications for failed batch
                    for email in batch:
                        classified_results.append({
                            'email_id': email.get('email_id', ''),
                            'subject': email.get('subject', ''),
                            'from': email.get('from', ''),
                            'date': email.get('date', ''),
                            'timestamp': email.get('timestamp', ''),
                            'is_classified': 'true',
                            'classification': 'classification_failed',
                            'is_travel_related': False
                        })
                    
                    self.classification_progress['processed'] = min(i + batch_size, len(unclassified_emails))
            
            # Save final results or handle stop condition
            if self._stop_flag.is_set():
                print("Saving partial results due to stop...")
                self._save_incremental_results(classified_results)
            else:
                print("Saving final results...")
                self._save_classification_results(classified_results, incremental=False)
            
            # Store final results
            travel_count = sum(1 for r in classified_results if r.get('is_travel_related', False))
            self.classification_progress['final_results'] = {
                'total_classified': len(classified_results),
                'travel_related': travel_count,
                'not_travel_related': len(classified_results) - travel_count,
                'test_file': self.test_file
            }
            
            print(f"Classification completed. {travel_count} travel-related emails found.")
            
        except Exception as e:
            print(f"Classification error: {e}")
            self.classification_progress['error'] = str(e)
        finally:
            self.classification_progress['finished'] = True
    
    def _load_unclassified_emails(self, limit: int) -> List[Dict]:
        """Load unclassified emails from cache"""
        if not os.path.exists(self.cache_file):
            return []
        
        unclassified = []
        with open(self.cache_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip already classified emails
                if row.get('is_classified', 'false').lower() == 'true':
                    continue
                
                unclassified.append(row)
                
                # Limit number of emails if specified
                if limit and len(unclassified) >= limit:
                    break
        
        return unclassified
    
    def _save_classification_results(self, results: List[Dict], incremental: bool = False):
        """Save classification results to test file and update original cache"""
        if not results:
            return
            
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.test_file), exist_ok=True)
        
        # 1. Save simplified results to test file (ID, subject, classification only)
        file_mode = 'a' if incremental and os.path.exists(self.test_file) else 'w'
        write_header = file_mode == 'w' or not os.path.exists(self.test_file)
        
        with open(self.test_file, file_mode, newline='', encoding='utf-8') as f:
            simple_headers = ['email_id', 'subject', 'classification']
            writer = csv.DictWriter(f, fieldnames=simple_headers)
            
            if write_header:
                writer.writeheader()
            
            for result in results:
                writer.writerow({
                    'email_id': result['email_id'],
                    'subject': result['subject'],
                    'classification': result['classification']
                })
        
        save_type = "incremental" if incremental else "final"
        print(f"Classification results ({save_type}) saved to: {self.test_file}")
        
        # 2. Update the original cache file to mark emails as classified
        if os.path.exists(self.cache_file):
            # Read all emails from cache
            all_emails = []
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                all_emails = list(reader)
            
            # Create a map of classified results
            classified_map = {r['email_id']: r['classification'] for r in results}
            
            # Update classified status and classification
            for email in all_emails:
                if email['email_id'] in classified_map:
                    email['is_classified'] = 'true'
                    email['classification'] = classified_map[email['email_id']]
            
            # Write back updated cache
            with open(self.cache_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.csv_headers)
                writer.writeheader()
                writer.writerows(all_emails)
            
            print(f"Updated {len(classified_map)} emails as classified in cache file")
    
    def _save_incremental_results(self, all_results: List[Dict]):
        """Save incremental results - only saves newly classified emails since last save"""
        if not all_results:
            return
            
        # Determine which results are new since last save
        existing_ids = set()
        if os.path.exists(self.test_file):
            with open(self.test_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing_ids = {row['email_id'] for row in reader if 'email_id' in row}
        
        # Only save new results
        new_results = [r for r in all_results if r['email_id'] not in existing_ids]
        
        if new_results:
            self._save_classification_results(new_results, incremental=True)
            print(f"Saved {len(new_results)} new results incrementally")
    
    def get_classification_stats(self) -> Dict:
        """Get statistics from classification test results"""
        if not os.path.exists(self.test_file):
            return {'total': 0, 'travel_related': 0, 'categories': {}}
        
        total = 0
        travel_related = 0
        categories = {}
        
        # Define travel-related categories
        travel_categories = {
            'flight', 'hotel', 'car_rental', 'train', 'cruise', 
            'tour', 'travel_insurance', 'flight_change', 
            'hotel_change', 'other_travel'
        }
        
        with open(self.test_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                
                classification = row.get('classification', 'unknown')
                categories[classification] = categories.get(classification, 0) + 1
                
                # Count as travel-related if it's in travel categories
                if classification in travel_categories:
                    travel_related += 1
        
        return {
            'total': total,
            'travel_related': travel_related,
            'not_travel_related': total - travel_related,
            'categories': categories,
            'test_file': self.test_file
        }