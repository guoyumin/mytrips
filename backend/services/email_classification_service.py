import os
from typing import List, Dict, Optional
from datetime import datetime
import threading
import time
import logging

from services.gemini_service import GeminiService
from lib.email_cache import EmailCache
from lib.email_classifier import EmailClassifier
from lib.config_manager import config_manager

# Configure logger
logger = logging.getLogger(__name__)

class EmailClassificationService:
    """Service for classifying emails using Gemini AI"""
    
    def __init__(self, cache_file: str = None, test_file: str = None, gemini_config_path: str = None):
        # Use config manager for paths
        if cache_file is None:
            cache_file = config_manager.get_cache_file_path()
        else:
            # Convert relative path to absolute if needed
            if not os.path.isabs(cache_file):
                cache_file = config_manager.get_absolute_path(cache_file)
        
        if test_file is None:
            test_file = config_manager.get_classification_test_file_path()
        if gemini_config_path is None:
            gemini_config_path = config_manager.get_gemini_config_path()
            
        # Initialize libraries
        self.email_cache = EmailCache(cache_file)
        self.test_file = test_file
        
        # Try to initialize email classifier
        try:
            logger.debug(f"Initializing email classifier with config: {gemini_config_path}")
            self.email_classifier = EmailClassifier(gemini_config_path)
            logger.debug("Email classifier initialized successfully")
        except Exception as e:
            logger.warning(f"Email classifier not available: {e}")
            self.email_classifier = None
        
        # Classification progress tracking
        self.classification_progress = {}
        self._stop_flag = threading.Event()
        self._classification_thread = None
        
        # Keep Gemini service for backward compatibility
        try:
            logger.debug("Initializing Gemini service for backward compatibility")
            self.gemini_service = GeminiService()
            logger.debug("Gemini service initialized successfully")
        except Exception as e:
            logger.warning(f"Gemini service not available: {e}")
            self.gemini_service = None
    
    def start_test_classification(self, limit: int = 1000) -> Dict:
        """Start test classification of emails in background"""
        logger.debug(f"Starting test classification with limit: {limit}")
        
        if self._classification_thread and self._classification_thread.is_alive():
            logger.warning("Classification already in progress")
            raise Exception("Classification already in progress")
        
        if not self.email_classifier and not self.gemini_service:
            logger.error("No classification service available")
            raise Exception("No classification service available. Please configure Gemini API key.")
        
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
            'batch_size': config_manager.get_batch_size(),
            'finished': False,
            'error': None,
            'start_time': datetime.now(),
            'estimated_cost': None
        }
        
        # Start classification thread
        logger.debug("Starting classification thread")
        self._classification_thread = threading.Thread(
            target=self._background_classification,
            args=(limit,),
            daemon=True
        )
        self._classification_thread.start()
        
        limit_msg = f"up to {limit} emails" if limit else "all unclassified emails"
        logger.info(f"Classification thread started for {limit_msg}")
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
        """Background classification process using new lib"""
        try:
            logger.info(f"Starting classification of emails (limit: {limit})")
            
            # Reset any previously failed classifications so they can be retried
            reset_count = self.email_cache.reset_failed_classifications()
            if reset_count > 0:
                logger.info(f"Reset {reset_count} previously failed classifications for retry")
            
            # Get unclassified emails using email_cache
            logger.debug(f"Getting unclassified emails with limit: {limit}")
            unclassified_emails = self.email_cache.get_emails(
                limit=limit, 
                filter_classified=False
            )
            logger.debug(f"Found {len(unclassified_emails) if unclassified_emails else 0} unclassified emails")
            
            if not unclassified_emails:
                logger.info("No unclassified emails found")
                self.classification_progress.update({
                    'finished': True,
                    'message': 'No unclassified emails found'
                })
                return
            
            # Update progress
            batch_size = self.classification_progress['batch_size']
            total_batches = (len(unclassified_emails) + batch_size - 1) // batch_size
            
            self.classification_progress.update({
                'total': len(unclassified_emails),
                'total_batches': total_batches
            })
            
            logger.info(f"Processing {len(unclassified_emails)} emails in {total_batches} batches of {batch_size} each")
            
            # Estimate cost if using new classifier
            if self.email_classifier:
                cost_info = self.email_classifier.estimate_cost(len(unclassified_emails))
                self.classification_progress['estimated_cost'] = cost_info['estimated_cost_usd']
                logger.info(f"Estimated cost: ${cost_info['estimated_cost_usd']}")
            
            # Process in batches
            all_results = []
            
            for batch_num in range(total_batches):
                if self._stop_flag.is_set():
                    print("Classification stopped by user")
                    break
                
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(unclassified_emails))
                batch_emails = unclassified_emails[start_idx:end_idx]
                
                self.classification_progress.update({
                    'current_batch': batch_num + 1,
                    'message': f'Processing batch {batch_num + 1}/{total_batches} ({len(batch_emails)} emails)...'
                })
                
                print(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_emails)} emails)...")
                
                # Classify batch
                if self.email_classifier:
                    # Use new email classifier
                    batch_results = self.email_classifier.classify_batch(batch_emails)
                else:
                    # Fallback to old gemini service
                    batch_results = self.gemini_service.classify_emails_batch(batch_emails)
                
                # Process results
                for email, result in zip(batch_emails, batch_results):
                    processed_result = {
                        'email_id': email['email_id'],
                        'subject': email.get('subject', ''),
                        'from': email.get('from', ''),
                        'classification': result.get('classification', 'classification_failed')
                    }
                    all_results.append(processed_result)
                
                # Update progress
                self.classification_progress['processed'] = len(all_results)
                print(f"Completed batch {batch_num + 1}/{total_batches}, processed {len(all_results)}/{len(unclassified_emails)} emails")
                
                # Save incremental results every 10 batches
                if (batch_num + 1) % 10 == 0:
                    self._save_results(all_results, incremental=True)
            
            # Save final results
            print("Saving final results...")
            self._save_results(all_results, incremental=False)
            
            # Update email cache with classifications
            # Separate successful and failed classifications
            successful_classifications = {}
            failed_count = 0
            
            for r in all_results:
                if r['classification'] == 'classification_failed':
                    failed_count += 1
                    logger.debug(f"Classification failed for email {r['email_id'][:10]}...")
                else:
                    successful_classifications[r['email_id']] = r['classification']
            
            # Update successful classifications as classified
            if successful_classifications:
                updated_count = self.email_cache.update_classifications(successful_classifications)
                logger.info(f"Updated {updated_count} emails as successfully classified")
            
            # Log failed classifications
            if failed_count > 0:
                logger.info(f"Found {failed_count} failed classifications - keeping as unclassified for retry")
            
            # Count travel-related emails
            travel_categories = {'flight', 'hotel', 'car_rental', 'train', 'cruise', 'tour', 'travel_insurance', 'flight_change', 'hotel_change', 'other_travel'}
            travel_count = sum(1 for r in all_results if r['classification'] in travel_categories)
            
            self.classification_progress.update({
                'finished': True,
                'classified_count': len(all_results),
                'message': f'Classification completed. {travel_count} travel-related emails found.'
            })
            
            print(f"Classification completed. {travel_count} travel-related emails found.")
            
        except Exception as e:
            print(f"Classification error: {e}")
            self.classification_progress.update({
                'finished': True,
                'error': str(e),
                'message': f'Classification failed: {str(e)}'
            })
    
    def _save_results(self, results: List[Dict], incremental: bool = False):
        """Save classification results to test file"""
        if not results:
            return
            
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.test_file), exist_ok=True)
        
        # Save simplified results to test file (ID, subject, classification only)
        import csv
        
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
    
    def get_classification_stats(self) -> Dict:
        """Get statistics from email cache"""
        return self.email_cache.get_statistics()