from typing import List, Dict, Optional
from datetime import datetime
import threading
import time
import logging

from backend.lib.email_cache_db import EmailCacheDB
from backend.lib.email_classifier import EmailClassifier
from backend.lib.config_manager import config_manager
from backend.lib.ai.ai_provider_with_fallback import AIProviderWithFallback
from backend.services.micro.classification_micro_service import ClassificationMicroService
from backend.database.config import SessionLocal
from backend.database.models import Email, ClassificationStats
from backend.constants import TRAVEL_CATEGORIES_SET, is_travel_category

# Configure logger
logger = logging.getLogger(__name__)

class EmailClassificationService:
    """Service for classifying emails using AI with automatic fallback"""
    
    def __init__(self):
        # Initialize email cache using database
        self.email_cache = EmailCacheDB()
        
        # Define provider order for first-tier (local model) classification
        # Using local models for fast initial screening
        self.first_tier_providers = [
            ('deepseek', 'powerful'),
            ('gemma3', 'powerful')
        ]
        
        # Define provider order for second-tier (cloud model) classification
        # Using more powerful models for accurate travel detection
        self.second_tier_providers = [
            ('gemini', 'fast'),      # Use Gemini for better accuracy
            ('openai', 'fast'),      # Fallback to OpenAI
            ('claude', 'fast')       # Final fallback
        ]
        
        # Try to initialize email classifiers
        try:
            # First tier classifier (local models)
            logger.debug("Initializing first-tier AI provider for initial screening")
            first_tier_ai = AIProviderWithFallback(self.first_tier_providers)
            first_tier_classifier = EmailClassifier(first_tier_ai)
            
            # Initialize first tier ClassificationMicroService
            self.classification_micro = ClassificationMicroService(first_tier_classifier)
            logger.info("First-tier ClassificationMicroService initialized successfully")
            
            # Second tier classifier (cloud models)
            logger.debug("Initializing second-tier AI provider for accurate classification")
            second_tier_ai = AIProviderWithFallback(self.second_tier_providers)
            second_tier_classifier = EmailClassifier(second_tier_ai)
            
            # Initialize second tier ClassificationMicroService
            self.second_tier_micro = ClassificationMicroService(second_tier_classifier)
            logger.info("Second-tier ClassificationMicroService initialized successfully")
            
            # Keep references for backward compatibility
            self.email_classifier = first_tier_classifier
            first_model_info = first_tier_ai.get_model_info()
            second_model_info = second_tier_ai.get_model_info()
            logger.info(f"Two-tier classification initialized. First tier: {first_model_info['model_name']}, Second tier: {second_model_info['model_name']}")
            
        except Exception as e:
            logger.warning(f"Email classifier not available: {e}")
            self.email_classifier = None
            self.classification_micro = None
            self.second_tier_micro = None
        
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
        """Start test classification of emails in background (legacy method using thread)"""
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
            
            if not self.classification_micro or not self.second_tier_micro:
                logger.error("No classification service available")
                raise Exception("No classification service available. Please configure AI provider.")
            
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
    
    def _classify_batch_with_microservice(self, 
                                         microservice: ClassificationMicroService,
                                         batch_email_ids: List[str],
                                         batch_size: int,
                                         tier_name: str) -> Dict:
        """
        Helper method to classify a batch of emails using a microservice
        
        Args:
            microservice: The classification microservice to use
            batch_email_ids: List of email IDs to classify
            batch_size: Batch size for microservice processing
            tier_name: Name of tier for logging (e.g., "First tier", "Second tier")
            
        Returns:
            Dict with classifications, cost_info, and errors
        """
        logger.info(f"{tier_name} classification for {len(batch_email_ids)} emails...")
        
        try:
            result = microservice.classify_emails(
                email_ids=batch_email_ids,
                batch_size=batch_size
            )
            
            classifications = result.get('classifications', [])
            
            # Log results
            if tier_name == "First tier":
                travel_count = sum(1 for c in classifications if is_travel_category(c.get('classification', '')))
                logger.info(f"{tier_name} identified {travel_count} potential travel emails out of {len(batch_email_ids)}")
            else:
                travel_count = sum(1 for c in classifications if is_travel_category(c.get('classification', '')))
                logger.info(f"{tier_name} verified {travel_count} out of {len(batch_email_ids)} as actual travel emails")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in {tier_name} classification: {e}")
            # Return error result
            return {
                'classifications': [],
                'cost_info': None,
                'errors': [{
                    'tier': tier_name,
                    'error': str(e),
                    'email_ids': batch_email_ids
                }]
            }
    
    def _update_cost_tracking(self, cost_info: Optional[Dict]):
        """
        Update cost tracking from classification result
        
        Args:
            cost_info: Cost information from classification result
        """
        if cost_info:
            self.classification_progress['actual_cost'] += cost_info.get('estimated_cost_usd', 0.0)
            self.classification_progress['total_tokens']['input'] += cost_info.get('input_tokens', 0)
            self.classification_progress['total_tokens']['output'] += cost_info.get('output_tokens', 0)
            self.classification_progress['total_tokens']['total'] += cost_info.get('total_tokens', 0)
    
    def _background_classification(self, limit: int):
        """Background classification process using two-tier ClassificationMicroService"""
        try:
            logger.info(f"Starting two-tier classification of emails (limit: {limit})")
            
            if not self.classification_micro or not self.second_tier_micro:
                raise Exception("Classification services not initialized")
            
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
            
            # Initialize tracking variables
            
            # Process in batches
            all_results = []
            total_errors = []
            
            for batch_num in range(total_batches):
                if self._stop_flag.is_set():
                    logger.info("Classification stopped by user")
                    break
                
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(unclassified_emails))
                batch_emails = unclassified_emails[start_idx:end_idx]
                
                # Extract email IDs for this batch
                batch_email_ids = [email['email_id'] for email in batch_emails]
                
                self.classification_progress.update({
                    'current_batch': batch_num + 1,
                    'message': f'Processing batch {batch_num + 1}/{total_batches} ({len(batch_emails)} emails) - First tier...'
                })
                
                logger.info(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_emails)} emails) - First tier classification...")
                
                # First tier classification - use local model for initial screening
                try:
                    first_tier_result = self._classify_batch_with_microservice(
                        self.classification_micro,
                        batch_email_ids,
                        batch_size,
                        "First tier"
                    )
                    
                    # Update cost tracking for first tier
                    self._update_cost_tracking(first_tier_result.get('cost_info'))
                    
                    # Filter travel-related emails from first tier
                    first_tier_classifications = first_tier_result.get('classifications', [])
                    travel_email_ids = []
                    first_tier_travel_map = {}  # Map email_id to first tier classification
                    
                    for classification in first_tier_classifications:
                        if is_travel_category(classification.get('classification', '')):
                            travel_email_ids.append(classification['email_id'])
                            first_tier_travel_map[classification['email_id']] = classification['classification']
                    
                    # Second tier classification - only for travel emails
                    final_classifications = []
                    
                    if travel_email_ids:
                        self.classification_progress.update({
                            'message': f'Processing batch {batch_num + 1}/{total_batches} - Second tier verification for {len(travel_email_ids)} emails...'
                        })
                        
                        second_tier_result = self._classify_batch_with_microservice(
                            self.second_tier_micro,
                            travel_email_ids,
                            batch_size,
                            "Second tier"
                        )
                        
                        # Update cost tracking for second tier
                        self._update_cost_tracking(second_tier_result.get('cost_info'))
                        
                        # Use second tier results for travel emails
                        second_tier_classifications = second_tier_result.get('classifications', [])
                        second_tier_map = {c['email_id']: c for c in second_tier_classifications}
                    else:
                        second_tier_map = {}
                    
                    # Combine results: use second tier for travel emails, mark others as not_travel
                    for classification in first_tier_classifications:
                        email_id = classification['email_id']
                        
                        if email_id in second_tier_map:
                            # Use second tier result for emails that went through second tier
                            final_classification = second_tier_map[email_id]
                        else:
                            # Non-travel emails from first tier
                            final_classification = {
                                'email_id': email_id,
                                'classification': 'not_travel'  # First tier said not travel
                            }
                        
                        final_classifications.append(final_classification)
                    
                    # Process results for progress tracking
                    for classification in final_classifications:
                        # Get email details from original list
                        email_data = next((e for e in batch_emails if e['email_id'] == classification['email_id']), {})
                        processed_result = {
                            'email_id': classification['email_id'],
                            'subject': email_data.get('subject', ''),
                            'from': email_data.get('from', ''),
                            'classification': classification.get('classification', 'classification_failed')
                        }
                        all_results.append(processed_result)
                    
                    # Collect errors
                    if first_tier_result.get('errors'):
                        total_errors.extend(first_tier_result['errors'])
                    if 'second_tier_result' in locals() and second_tier_result.get('errors'):
                        total_errors.extend(second_tier_result['errors'])
                    
                    # Update progress
                    self.classification_progress['processed'] = len(all_results)
                    logger.info(f"Completed batch {batch_num + 1}/{total_batches}, processed {len(all_results)}/{len(unclassified_emails)} emails")
                    
                    # Save final classifications to database
                    if final_classifications:
                        self._save_batch_classifications(final_classifications)
                    
                except Exception as e:
                    logger.error(f"Error processing batch {batch_num + 1}: {e}")
                    # Mark all emails in this batch as failed
                    for email in batch_emails:
                        processed_result = {
                            'email_id': email['email_id'],
                            'subject': email.get('subject', ''),
                            'from': email.get('from', ''),
                            'classification': 'classification_failed'
                        }
                        all_results.append(processed_result)
                    total_errors.append({
                        'batch': batch_num + 1,
                        'error': str(e)
                    })
            
            # Count final results for summary
            failed_count = len([r for r in all_results if r['classification'] == 'classification_failed'])
            successful_count = len(all_results) - failed_count
            
            # Handle errors
            if total_errors:
                logger.error(f"Classification errors: {total_errors}")
                
            # Log final cost if available
            if self.classification_progress.get('actual_cost'):
                logger.info(f"Two-tier classification completed: {successful_count} successful, {failed_count} failed. Total cost: ${self.classification_progress['actual_cost']:.4f}")
            else:
                logger.info(f"Two-tier classification completed: {successful_count} successful, {failed_count} failed")
            
            if failed_count > 0:
                logger.info(f"Found {failed_count} failed classifications - keeping as unclassified for retry")
            
            # Count travel-related emails in final results
            travel_count = sum(1 for r in all_results if is_travel_category(r['classification']))
            
            with self._lock:
                self.classification_progress.update({
                    'is_running': False,
                    'finished': True,
                    'classified_count': len(all_results),
                    'message': f'Two-tier classification completed. {travel_count} travel-related emails found.'
                })
            
            logger.info(f"Two-tier classification completed. {travel_count} travel-related emails found.")
            
        except Exception as e:
            logger.error(f"Classification error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            with self._lock:
                self.classification_progress.update({
                    'is_running': False,
                    'finished': True,
                    'error': str(e),
                    'message': f'Classification failed: {str(e)}'
                })
    
    def _save_batch_classifications(self, classifications: List[Dict]):
        """Save classification results to database"""
        db = SessionLocal()
        try:
            for classification in classifications:
                email = db.query(Email).filter_by(
                    email_id=classification['email_id']
                ).first()
                
                if email:
                    email.classification = classification.get('classification', 'classification_failed')
                    email.is_classified = True
                    
            db.commit()
            logger.info(f"Saved {len(classifications)} classifications to database")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save classifications: {e}")
            raise
        finally:
            db.close()
    
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