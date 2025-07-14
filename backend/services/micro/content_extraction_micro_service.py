"""
Content Extraction Microservice - Handles email content extraction from Gmail
"""
import json
import logging
from typing import List, Dict

from backend.lib.email_content_extractor import EmailContentExtractor
from backend.database.models import Email, EmailContent
from backend.constants import is_travel_category
from .base_micro_service import BaseMicroService

logger = logging.getLogger(__name__)


class ContentExtractionMicroService(BaseMicroService):
    """
    Microservice for extracting email content
    
    - Reads email IDs from database
    - Extracts content from Gmail
    - Returns results without writing to database
    """
    
    def __init__(self, gmail_client):
        """
        Initialize content extraction microservice
        
        Args:
            gmail_client: Initialized Gmail client instance
        """
        super().__init__()
        # Initialize with appropriate data root path
        from backend.lib.config_manager import config_manager
        data_root = config_manager.get_absolute_path('data/email_content')
        self.extractor = EmailContentExtractor(gmail_client, data_root)
    
    def extract_content(self, email_ids: List[str]) -> Dict:
        """
        Extract content for specified emails
        
        Args:
            email_ids: List of email IDs to extract content for
            
        Returns:
            {
                'results': [
                    {
                        'email_id': str,
                        'content_text': str,
                        'content_html': str,
                        'has_attachments': bool,
                        'attachments': List[Dict],
                        'attachments_count': int,
                        'status': 'success' | 'failed' | 'skipped',
                        'error': str or None,
                        'skip_reason': str or None
                    }
                ],
                'success_count': int,
                'failed_count': int,
                'skipped_count': int
            }
        """
        self.log_operation('extract_content', {
            'email_count': len(email_ids)
        })
        
        results = []
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        # Check which emails actually need extraction
        emails_to_extract = self._filter_emails_for_extraction(email_ids)
        
        for email_id in email_ids:
            if email_id not in emails_to_extract:
                # Skip non-travel or already extracted emails
                results.append({
                    'email_id': email_id,
                    'status': 'skipped',
                    'skip_reason': emails_to_extract.get(email_id, 'Not a travel email or already extracted')
                })
                skipped_count += 1
                continue
            
            try:
                # Use existing extractor logic
                extracted_data = self.extractor.extract_email(email_id)
                
                if not extracted_data:
                    raise Exception(f"Extraction returned None for email {email_id}")
                
                # Optional: Save content to files
                content_paths = self.extractor.save_email_content(
                    email_id,
                    extracted_data.get('text_content', ''),
                    extracted_data.get('html_content', '')
                )
                
                results.append({
                    'email_id': email_id,
                    'content_text': extracted_data.get('text_content', ''),
                    'content_html': extracted_data.get('html_content', ''),
                    'has_attachments': extracted_data.get('has_attachments', False),
                    'attachments': extracted_data.get('attachments', []),
                    'attachments_count': len(extracted_data.get('attachments', [])),
                    'status': 'success',
                    'error': None
                })
                success_count += 1
                logger.info(f"Successfully extracted content for email {email_id}")
                
            except Exception as e:
                logger.error(f"Failed to extract content for email {email_id}: {e}")
                results.append({
                    'email_id': email_id,
                    'status': 'failed',
                    'error': str(e)
                })
                failed_count += 1
        
        logger.info(f"Content extraction complete: {success_count} success, {failed_count} failed, {skipped_count} skipped")
        
        return {
            'results': results,
            'success_count': success_count,
            'failed_count': failed_count,
            'skipped_count': skipped_count
        }
    
    @BaseMicroService.with_db
    def _filter_emails_for_extraction(self, db, email_ids: List[str]) -> Dict[str, bool]:
        """
        Filter emails to determine which need content extraction
        
        Args:
            db: Database session (injected by decorator)
            email_ids: List of email IDs to check
            
        Returns:
            Dict mapping email_id to whether it needs extraction
        """
        # Get email info with content status
        emails = db.query(Email).outerjoin(EmailContent).filter(
            Email.email_id.in_(email_ids)
        ).all()
        
        emails_to_extract = {}
        
        for email in emails:
            # Skip non-travel emails
            if not is_travel_category(email.classification):
                continue
            
            # Check if content already extracted
            if email.email_content and email.email_content.extraction_status == 'completed':
                continue
            
            # This email needs extraction
            emails_to_extract[email.email_id] = True
        
        return emails_to_extract
    
    @BaseMicroService.with_db
    def get_emails_needing_content(self, db, limit: int = None) -> List[str]:
        """
        Get IDs of travel emails that need content extraction
        
        Args:
            db: Database session (injected by decorator)
            limit: Maximum number of IDs to return
            
        Returns:
            List of email IDs
        """
        from backend.constants import TRAVEL_CATEGORIES
        
        # Use subquery to find emails with completed extraction
        extracted_ids = db.query(EmailContent.email_id).filter(
            EmailContent.extraction_status.in_(['completed', 'not_required'])
        ).subquery()
        
        # Query travel emails not in extracted list
        query = db.query(Email.email_id).filter(
            Email.classification.in_(TRAVEL_CATEGORIES),
            ~Email.email_id.in_(extracted_ids)
        )
        
        if limit:
            query = query.limit(limit)
        
        emails = query.all()
        return [email[0] for email in emails]