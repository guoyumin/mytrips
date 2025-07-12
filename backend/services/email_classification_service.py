from typing import List, Dict, Optional
from datetime import datetime
import threading
import time
import logging

from backend.lib.email_cache_db import EmailCacheDB
from backend.lib.email_classifier import EmailClassifier
from backend.lib.config_manager import config_manager
from backend.lib.ai.ai_provider_with_fallback import AIProviderWithFallback

# Configure logger
logger = logging.getLogger(__name__)

class EmailClassificationService:
    """Service for classifying emails using AI with automatic fallback"""
    
    def __init__(self):
        # Initialize email cache using database
        self.email_cache = EmailCacheDB()
        
        # Define fallback order for email classification
        # Start with fast models for cost efficiency
        self.provider_fallback_order = [
            ('deepseek', 'powerful'),
            ('gemma3', 'powerful')
        ]
        
        # Try to initialize email classifier with fallback support
        try:
            logger.debug("Initializing AI provider with fallback for email classification")
            ai_provider = AIProviderWithFallback(self.provider_fallback_order)
            self.email_classifier = EmailClassifier(ai_provider)
            model_info = ai_provider.get_model_info()
            logger.debug(f"Email classifier initialized with fallback support. Primary model: {model_info['model_name']}")
        except Exception as e:
            logger.warning(f"Email classifier not available: {e}")
            self.email_classifier = None
        
        # Classification progress tracking with thread safety
        self.classification_progress = {
            'is_running': False,
            'total': 0,
            'processed': 0,
            'finished': False,
            'error': None
        }
        self._stop_flag = threading.Event()
        self._classification_thread = None
        self._lock = threading.Lock()  # Add thread lock for safety
        
        # No longer need separate Gemini service - AI provider handles all models
        self.ai_provider = None
        try:
            if self.email_classifier:
                self.ai_provider = self.email_classifier.ai_provider
            logger.debug("Gemini service initialized successfully")
        except Exception as e:
            logger.warning(f"Gemini service not available: {e}")
            self.gemini_service = None
    
    def start_test_classification(self, limit: int = 1000) -> Dict:
        """Start test classification of emails in background"""
        logger.debug(f"Starting test classification with limit: {limit}")
        
        with self._lock:
            # Check if classification is already running
            if self.classification_progress.get('is_running', False):
                logger.warning("Classification already in progress")
                return {"started": False, "message": "Classification already in progress"}
            
            # Double-check thread status
            if self._classification_thread and self._classification_thread.is_alive():
                logger.warning("Classification thread already running")
                return {"started": False, "message": "Classification already in progress"}
            
            if not self.email_classifier and not self.gemini_service:
                logger.error("No classification service available")
                raise Exception("No classification service available. Please configure Gemini API key.")
            
            # Reset stop flag
            self._stop_flag.clear()
            
            # Initialize progress tracking
            self.classification_progress = {
                'is_running': True,
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
        with self._lock:
            self._stop_flag.set()
            if self.classification_progress.get('is_running', False):
                self.classification_progress['is_running'] = False
                self.classification_progress['finished'] = True
                self.classification_progress['message'] = 'Classification stopped by user'
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
                with self._lock:
                    self.classification_progress.update({
                        'is_running': False,
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
            
            # Initialize actual cost tracking
            self.classification_progress['actual_cost'] = 0.0
            self.classification_progress['total_tokens'] = {
                'input': 0,
                'output': 0,
                'total': 0
            }
            
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
                    batch_response = self.email_classifier.classify_batch(batch_emails)
                    batch_results = batch_response['classifications']
                    
                    # Update cost tracking if available
                    if batch_response.get('cost_info'):
                        cost_info = batch_response['cost_info']
                        self.classification_progress['actual_cost'] += cost_info.get('estimated_cost_usd', 0.0)
                        self.classification_progress['total_tokens']['input'] += cost_info.get('input_tokens', 0)
                        self.classification_progress['total_tokens']['output'] += cost_info.get('output_tokens', 0)
                        self.classification_progress['total_tokens']['total'] += cost_info.get('total_tokens', 0)
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
                
                # Update database with batch results immediately
                batch_classifications = {}
                for email, result in zip(batch_emails, batch_results):
                    email_id = email['email_id']
                    classification = result.get('classification', 'classification_failed')
                    batch_classifications[email_id] = classification
                
                if batch_classifications:
                    try:
                        updated_count = self.email_cache.update_classifications(batch_classifications)
                        print(f"Updated {updated_count} emails in database for batch {batch_num + 1}")
                    except Exception as e:
                        print(f"Error updating database for batch {batch_num + 1}: {e}")
                        logger.error(f"Error updating database for batch {batch_num + 1}: {e}")
            
            # Database already updated - no need to save to CSV files
            
            # Count final results for summary
            failed_count = sum(1 for r in all_results if r['classification'] == 'classification_failed')
            successful_count = len(all_results) - failed_count
            
            # Log final cost if available
            if self.classification_progress.get('actual_cost'):
                logger.info(f"Classification completed: {successful_count} successful, {failed_count} failed. Total cost: ${self.classification_progress['actual_cost']:.4f}")
            else:
                logger.info(f"Classification completed: {successful_count} successful, {failed_count} failed")
            
            if failed_count > 0:
                logger.info(f"Found {failed_count} failed classifications - keeping as unclassified for retry")
            
            # Count travel-related emails
            travel_categories = {'flight', 'hotel', 'car_rental', 'train', 'cruise', 'tour', 'travel_insurance', 'flight_change', 'hotel_change', 'other_travel'}
            travel_count = sum(1 for r in all_results if r['classification'] in travel_categories)
            
            with self._lock:
                self.classification_progress.update({
                    'is_running': False,
                    'finished': True,
                    'classified_count': len(all_results),
                    'message': f'Classification completed. {travel_count} travel-related emails found.'
                })
            
            print(f"Classification completed. {travel_count} travel-related emails found.")
            
        except Exception as e:
            print(f"Classification error: {e}")
            with self._lock:
                self.classification_progress.update({
                    'is_running': False,
                    'finished': True,
                    'error': str(e),
                    'message': f'Classification failed: {str(e)}'
                })
    
    
    def get_classification_stats(self) -> Dict:
        """Get statistics from email cache"""
        return self.email_cache.get_statistics()
    
    def reset_all_classifications(self) -> Dict:
        """重置所有邮件分类状态"""
        from backend.database.config import SessionLocal
        from backend.database.models import Email, ClassificationStats
        
        db = SessionLocal()
        try:
            # 确保没有正在运行的分类任务
            if self.classification_progress.get('is_running'):
                return {
                    'success': False,
                    'message': '邮件分类正在进行中，请先停止分类'
                }
            
            # 重置所有邮件的分类状态
            reset_count = db.query(Email).update({
                'is_classified': False,
                'classification': None
            }, synchronize_session=False)
            
            # 清除分类统计数据
            stats_count = db.query(ClassificationStats).delete()
            
            db.commit()
            
            # 重置进度状态
            with self._lock:
                self.classification_progress = {
                    'is_running': False,
                    'total_emails': 0,
                    'processed_emails': 0,
                    'classified_count': 0,
                    'finished': False,
                    'error': None,
                    'message': ''
                }
            
            logger.info(f"成功重置 {reset_count} 封邮件的分类状态")
            
            return {
                'success': True,
                'reset_count': reset_count,
                'stats_cleared': stats_count,
                'message': f'成功重置 {reset_count} 封邮件的分类状态'
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"重置分类失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'重置分类失败: {str(e)}'
            }
        finally:
            db.close()