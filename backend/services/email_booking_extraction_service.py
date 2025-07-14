"""
Email Booking Extraction Service - Step 1: Extract booking information from individual emails
"""
import threading
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from backend.database.config import SessionLocal
from backend.database.models import Email, EmailContent
from backend.lib.ai.ai_provider_with_fallback import AIProviderWithFallback
from backend.lib.booking_extractor import BookingExtractor
from backend.constants import TRAVEL_CATEGORIES

logger = logging.getLogger(__name__)


class EmailBookingExtractionService:
    """Service for extracting booking information from individual travel emails"""
    
    def __init__(self):
        self.ai_provider: Optional[AIProviderWithFallback] = None
        self.booking_extractor: Optional[BookingExtractor] = None
        
        # Provider fallback order: deepseek-powerful -> gemini-fast -> openai-fast
        self.provider_fallback_order = [
            ('gemini', 'fast'),
            ('openai', 'fast')
        ]
        
        try:
            # Create AI provider with fallback support
            self.ai_provider = AIProviderWithFallback(self.provider_fallback_order)
            self.booking_extractor = BookingExtractor(self.ai_provider)
            model_info = self.ai_provider.get_model_info()
            logger.info(f"Booking extraction AI provider initialized with fallback support. Primary model: {model_info['model_name']}")
        except Exception as e:
            logger.error(f"Failed to initialize AI provider with fallback: {e}")
            self.ai_provider = None
            self.booking_extractor = None
        
        # Progress tracking with thread safety
        self.extraction_progress = {
            'is_running': False,
            'total_emails': 0,
            'processed_emails': 0,
            'extracted_count': 0,
            'failed_count': 0,
            'current_batch': 0,
            'total_batches': 0,
            'finished': False,
            'error': None,
            'message': ''
        }
        self._stop_flag = threading.Event()
        self._extraction_thread = None
        self._lock = threading.Lock()
    
    def start_extraction(self, date_range: Optional[Dict] = None, email_ids: Optional[List[str]] = None) -> Dict:
        """Start booking information extraction process
        
        Args:
            date_range: Optional date range filter (ignored if email_ids provided)
            email_ids: Optional list of specific email IDs to process
        """
        with self._lock:
            if self.extraction_progress.get('is_running', False):
                return {"started": False, "message": "Booking extraction already in progress"}
            
            if self._extraction_thread and self._extraction_thread.is_alive():
                return {"started": False, "message": "Extraction thread already running"}
            
            if not self.ai_provider:
                return {"started": False, "message": "AI provider not available"}
            
            # Reset progress
            self._stop_flag.clear()
            self.extraction_progress = {
                'is_running': True,
                'total_emails': 0,
                'processed_emails': 0,
                'extracted_count': 0,
                'failed_count': 0,
                'current_batch': 0,
                'total_batches': 0,
                'finished': False,
                'error': None,
                'message': 'Starting booking extraction...',
                'start_time': datetime.now()
            }
            
            # Start background thread
            self._extraction_thread = threading.Thread(
                target=self._background_extraction,
                args=(date_range, email_ids),
                daemon=True
            )
            self._extraction_thread.start()
            
            message = f"Booking extraction started for {len(email_ids) if email_ids else 'all eligible'} emails"
            return {"started": True, "message": message}
    
    def stop_extraction(self) -> str:
        """Stop ongoing extraction process"""
        with self._lock:
            self._stop_flag.set()
            if self.extraction_progress.get('is_running', False):
                self.extraction_progress['is_running'] = False
                self.extraction_progress['finished'] = True
                self.extraction_progress['message'] = 'Extraction stopped by user'
        return "Stop signal sent"
    
    def get_extraction_progress(self) -> Dict:
        """Get current extraction progress"""
        progress = self.extraction_progress.copy()
        
        # Calculate progress percentage
        if progress['total_emails'] > 0:
            progress['progress'] = int((progress['processed_emails'] / progress['total_emails']) * 100)
        else:
            progress['progress'] = 0
            
        return progress
    
    def _sync_non_travel_emails_status(self, db: Session):
        """Sync booking extraction status for non-travel emails"""
        try:
            # First get the email IDs of non-travel emails
            non_travel_email_ids = [row[0] for row in db.query(Email.email_id).filter(
                ~Email.classification.in_(TRAVEL_CATEGORIES)
            ).all()]
            
            if non_travel_email_ids:
                # Update non-travel emails with pending booking extraction status to 'not_travel'
                updated_count = db.query(EmailContent).filter(
                    EmailContent.email_id.in_(non_travel_email_ids),
                    EmailContent.booking_extraction_status == 'pending'
                ).update({
                    'booking_extraction_status': 'not_travel',
                    'booking_extraction_error': 'Not a travel email'
                }, synchronize_session=False)
                
                if updated_count > 0:
                    db.commit()
                    logger.info(f"Updated {updated_count} non-travel emails to booking_extraction_status='not_travel'")
                
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to sync non-travel emails status: {e}")
            raise
    
    def _background_extraction(self, date_range: Optional[Dict] = None, email_ids: Optional[List[str]] = None):
        """Background process for booking extraction
        
        Args:
            date_range: Optional date range filter (ignored if email_ids provided)
            email_ids: Optional list of specific email IDs to process
        """
        db = SessionLocal()
        try:
            # First, sync non-travel emails that have pending booking extraction status
            self._sync_non_travel_emails_status(db)
            
            if email_ids:
                # Use specific email IDs provided
                emails = db.query(Email).join(EmailContent).filter(
                    Email.email_id.in_(email_ids),
                    EmailContent.extraction_status == 'completed'
                ).order_by(Email.timestamp.asc()).all()
                logger.info(f"Processing {len(emails)} specific emails for booking extraction")
            else:
                # Fetch all travel-related emails with content but no booking extraction
                query = db.query(Email).join(EmailContent).filter(
                    Email.classification.in_(TRAVEL_CATEGORIES),
                    EmailContent.extraction_status == 'completed',
                    EmailContent.booking_extraction_status.in_(['pending', 'failed'])
                )
                
                if date_range:
                    if 'start_date' in date_range:
                        query = query.filter(Email.timestamp >= date_range['start_date'])
                    if 'end_date' in date_range:
                        query = query.filter(Email.timestamp <= date_range['end_date'])
                
                # Order by timestamp for chronological processing
                emails = query.order_by(Email.timestamp.asc()).all()
            
            if not emails:
                with self._lock:
                    self.extraction_progress.update({
                        'finished': True,
                        'is_running': False,
                        'message': 'No emails found that need booking extraction'
                    })
                return
            
            # Update progress
            self.extraction_progress['total_emails'] = len(emails)
            
            # Skip cost estimation for now since we're using AI provider interface
            # TODO: Add cost estimation to AI provider interface
            
            self.extraction_progress['message'] = f'Found {len(emails)} emails to extract booking information'
            
            # Process emails in smaller batches for booking extraction (10 emails per batch)
            batch_size = 10
            total_batches = (len(emails) + batch_size - 1) // batch_size
            self.extraction_progress['total_batches'] = total_batches
            
            extracted_count = 0
            failed_count = 0
            
            for batch_num in range(total_batches):
                if self._stop_flag.is_set():
                    break
                
                start_idx = batch_num * batch_size
                end_idx = min((batch_num + 1) * batch_size, len(emails))
                batch_emails = emails[start_idx:end_idx]
                
                self.extraction_progress['current_batch'] = batch_num + 1
                self.extraction_progress['message'] = f'Processing batch {batch_num + 1}/{total_batches}'
                
                # Reset to primary provider for each new batch
                if batch_num > 0:  # Only reset after first batch
                    logger.info(f"Resetting to primary provider for batch {batch_num + 1}")
                    self.ai_provider.reset_to_primary()
                
                # Process each email individually in this batch
                for email in batch_emails:
                    if self._stop_flag.is_set():
                        break
                    
                    try:
                        success = self._extract_single_email_booking(email, db)
                        if success:
                            extracted_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to extract booking info from email {email.email_id}: {e}")
                        failed_count += 1
                    
                    self.extraction_progress['processed_emails'] += 1
                    self.extraction_progress['extracted_count'] = extracted_count
                    self.extraction_progress['failed_count'] = failed_count
            
            # Mark as finished
            with self._lock:
                self.extraction_progress.update({
                    'finished': True,
                    'is_running': False,
                    'message': f'Extraction completed. {extracted_count} extracted, {failed_count} failed.'
                })
            
        except Exception as e:
            logger.error(f"Booking extraction failed: {e}")
            with self._lock:
                self.extraction_progress.update({
                    'finished': True,
                    'is_running': False,
                    'error': str(e),
                    'message': f'Extraction failed: {str(e)}'
                })
        finally:
            db.close()
    
    def _extract_single_email_booking(self, email: Email, db: Session) -> bool:
        """Extract booking information from a single email with provider fallback"""
        content = email.email_content
        if not content:
            logger.warning(f"No content found for email {email.email_id}")
            return False
        
        # Update status to extracting
        content.booking_extraction_status = 'extracting'
        db.commit()
        
        try:
            # Prepare email data for booking extractor
            email_data = {
                'email_id': email.email_id,
                'subject': email.subject,
                'sender': email.sender,
                'date': email.date,
                'classification': email.classification,
                'content_text': content.content_text,
                'content_html': content.content_html,
                'attachments': json.loads(content.attachments_info or '[]')
            }
            
            # Use booking extractor
            result = self.booking_extractor.extract_booking(email_data)
            
            # Check for errors
            if result.get('error'):
                raise Exception(result['error'])
            
            booking_info = result.get('booking_info')
            
            if booking_info:
                # First check if this email was correctly classified as travel
                if booking_info.get('is_travel') == False:
                    # This email is not travel-related, update classification
                    logger.warning(f"Email {email.email_id} was misclassified as travel. Actual category: {booking_info.get('actual_category', 'not_travel')}")
                    
                    # Update email classification in database
                    email.classification = booking_info.get('actual_category', 'not_travel')
                    db.commit()
                    
                    # Mark as non-travel in both extraction and booking extraction
                    content.extracted_booking_info = json.dumps(booking_info, ensure_ascii=False)
                    content.booking_extraction_status = 'not_travel'
                    content.booking_extraction_error = booking_info.get('reason', 'Not a travel email')
                    content.extraction_status = 'not_required'  # Also update extraction status
                    db.commit()
                    
                    logger.info(f"Email {email.email_id} reclassified as: {email.classification}")
                    return True
                    
                # Check if this is a non-booking email
                elif booking_info.get('booking_type') is None:
                    # This is a non-booking travel email (reminder, marketing, etc.)
                    content.extracted_booking_info = json.dumps(booking_info, ensure_ascii=False)
                    content.booking_extraction_status = 'no_booking'
                    content.booking_extraction_error = booking_info.get('reason', 'Non-booking email')
                    db.commit()
                    
                    logger.info(f"Email {email.email_id} identified as non-booking: {booking_info.get('non_booking_type', 'unknown')}")
                    return True
                else:
                    # This is a booking email with extracted information
                    content.extracted_booking_info = json.dumps(booking_info, ensure_ascii=False)
                    content.booking_extraction_status = 'completed'
                    content.booking_extraction_error = None
                    db.commit()
                    
                    logger.info(f"Successfully extracted booking info from email {email.email_id}")
                    return True
            else:
                # Failed to parse
                raise Exception("Failed to parse booking information from AI response")
                
        except Exception as e:
            # All providers have been exhausted by AIProviderWithFallback
            logger.error(f"Failed to extract booking from email {email.email_id}: {e}")
            content.booking_extraction_status = 'failed'
            content.booking_extraction_error = str(e)
            db.commit()
            return False
    
    
    def reset_all_booking_extraction(self) -> Dict:
        """重置所有booking提取状态"""
        from backend.database.config import SessionLocal
        from backend.database.models import EmailContent
        
        db = SessionLocal()
        try:
            # 确保没有正在运行的提取任务
            if self.extraction_progress.get('is_running'):
                return {
                    'success': False,
                    'message': 'Booking提取正在进行中，请先停止提取'
                }
            
            # Import Email model
            from backend.database.models import Email
            
            # Get travel and non-travel email IDs
            travel_email_ids = [row[0] for row in db.query(Email.email_id).filter(
                Email.classification.in_(TRAVEL_CATEGORIES)
            ).all()]
            
            non_travel_email_ids = [row[0] for row in db.query(Email.email_id).filter(
                ~Email.classification.in_(TRAVEL_CATEGORIES)
            ).all()]
            
            # Reset travel emails to pending
            travel_reset_count = 0
            if travel_email_ids:
                travel_reset_count = db.query(EmailContent).filter(
                    EmailContent.email_id.in_(travel_email_ids)
                ).update({
                    'booking_extraction_status': 'pending',
                    'booking_extraction_error': None,
                    'extracted_booking_info': None
                }, synchronize_session=False)
            
            # Mark non-travel emails as not_travel
            non_travel_reset_count = 0
            if non_travel_email_ids:
                non_travel_reset_count = db.query(EmailContent).filter(
                    EmailContent.email_id.in_(non_travel_email_ids)
                ).update({
                    'booking_extraction_status': 'not_travel',
                    'booking_extraction_error': 'Not a travel email',
                    'extracted_booking_info': None
                }, synchronize_session=False)
            
            reset_count = travel_reset_count + non_travel_reset_count
            db.commit()
            
            # 重置进度状态
            with self._lock:
                self.extraction_progress = {
                    'is_running': False,
                    'total_emails': 0,
                    'processed_emails': 0,
                    'extracted_count': 0,
                    'failed_count': 0,
                    'finished': False,
                    'error': None,
                    'message': ''
                }
            
            logger.info(f"成功重置 {reset_count} 条booking提取记录 (旅行邮件: {travel_reset_count}, 非旅行邮件: {non_travel_reset_count})")
            
            return {
                'success': True,
                'reset_count': reset_count,
                'travel_reset_count': travel_reset_count,
                'non_travel_reset_count': non_travel_reset_count,
                'message': f'成功重置 {reset_count} 条booking提取记录 (旅行邮件: {travel_reset_count}, 非旅行邮件: {non_travel_reset_count})'
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"重置booking提取失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'重置booking提取失败: {str(e)}'
            }
        finally:
            db.close()