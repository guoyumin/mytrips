"""
Booking Extraction Microservice - Handles booking information extraction using AI
"""
import json
import logging
from typing import List, Dict

from backend.lib.booking_extractor import BookingExtractor
from backend.database.models import Email, EmailContent
from backend.constants import TRAVEL_CATEGORIES
from .base_micro_service import BaseMicroService

logger = logging.getLogger(__name__)


class BookingExtractionMicroService(BaseMicroService):
    """
    Microservice for extracting booking information
    
    - Reads email content from database
    - Extracts booking info using AI
    - Returns results without writing to database
    """
    
    def __init__(self, ai_provider):
        """
        Initialize booking extraction microservice
        
        Args:
            ai_provider: AI provider instance for extraction
        """
        super().__init__()
        self.booking_extractor = BookingExtractor(ai_provider)
    
    def extract_bookings(self, email_ids: List[str]) -> Dict:
        """
        Extract booking information from specified emails
        
        Args:
            email_ids: List of email IDs to extract bookings from
            
        Returns:
            {
                'bookings': [
                    {
                        'email_id': str,
                        'is_travel': bool,
                        'booking_info': Dict or None,
                        'actual_category': str (if misclassified),
                        'reason': str (if not travel or no booking),
                        'status': 'success' | 'failed' | 'skipped',
                        'error': str or None,
                        'skip_reason': str or None
                    }
                ],
                'success_count': int,
                'failed_count': int,
                'skipped_count': int,
                'reclassified_count': int  # Emails found to be non-travel
            }
        """
        self.log_operation('extract_bookings', {
            'email_count': len(email_ids)
        })
        
        # Get emails with content from database
        emails_data = self._get_emails_with_content(email_ids)
        
        results = []
        success_count = 0
        failed_count = 0
        skipped_count = 0
        reclassified_count = 0
        
        for email_data in emails_data:
            if email_data.get('skip_reason'):
                # Skip emails without content or non-travel emails
                results.append({
                    'email_id': email_data['email_id'],
                    'status': 'skipped',
                    'skip_reason': email_data['skip_reason']
                })
                skipped_count += 1
                continue
            
            try:
                # Extract booking using BookingExtractor
                result = self.booking_extractor.extract_booking(email_data)
                
                # Check if email was reclassified as non-travel
                if not result.get('is_travel', True):
                    reclassified_count += 1
                
                results.append({
                    'email_id': email_data['email_id'],
                    'status': 'success',
                    **result
                })
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to extract booking from email {email_data['email_id']}: {e}")
                results.append({
                    'email_id': email_data['email_id'],
                    'status': 'failed',
                    'error': str(e)
                })
                failed_count += 1
        
        logger.info(f"Booking extraction complete: {success_count} success, {failed_count} failed, {skipped_count} skipped, {reclassified_count} reclassified")
        
        return {
            'bookings': results,
            'success_count': success_count,
            'failed_count': failed_count,
            'skipped_count': skipped_count,
            'reclassified_count': reclassified_count
        }
    
    @BaseMicroService.with_db
    def _get_emails_with_content(self, db, email_ids: List[str]) -> List[Dict]:
        """
        Get email data with content from database
        
        Args:
            db: Database session (injected by decorator)
            email_ids: List of email IDs
            
        Returns:
            List of email data dictionaries
        """
        # Query emails with their content
        emails = db.query(Email, EmailContent).outerjoin(EmailContent).filter(
            Email.email_id.in_(email_ids)
        ).all()
        
        emails_data = []
        for email, content in emails:
            # Skip non-travel emails
            if email.classification not in TRAVEL_CATEGORIES:
                emails_data.append({
                    'email_id': email.email_id,
                    'skip_reason': f'Not a travel email: {email.classification}'
                })
                continue
            
            # Skip emails without content
            if not content or not content.extraction_status == 'completed':
                emails_data.append({
                    'email_id': email.email_id,
                    'skip_reason': 'No extracted content available'
                })
                continue
            
            # Prepare email data for booking extraction
            emails_data.append({
                'email_id': email.email_id,
                'subject': email.subject,
                'sender': email.sender,
                'date': email.date,
                'classification': email.classification,
                'content_text': content.content_text,
                'content_html': content.content_html,
                'attachments': json.loads(content.attachments_info or '[]')
            })
        
        return emails_data
    
    @BaseMicroService.with_db
    def get_emails_needing_booking_extraction(self, db, limit: int = None) -> List[str]:
        """
        Get IDs of emails that need booking extraction
        
        Args:
            db: Database session (injected by decorator)
            limit: Maximum number of IDs to return
            
        Returns:
            List of email IDs
        """
        # Query travel emails with extracted content but no booking extraction
        query = db.query(Email.email_id).join(EmailContent).filter(
            Email.classification.in_(TRAVEL_CATEGORIES),
            EmailContent.extraction_status == 'completed',
            EmailContent.booking_extraction_status.in_(['pending', 'failed'])
        )
        
        if limit:
            query = query.limit(limit)
        
        emails = query.all()
        return [email[0] for email in emails]