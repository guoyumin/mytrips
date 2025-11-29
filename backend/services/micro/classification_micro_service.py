"""
Classification Microservice - Handles email classification using AI
"""
import logging
from typing import List, Dict, Optional

from backend.lib.email_classifier import EmailClassifier
from backend.database.models import Email
from .base_micro_service import BaseMicroService

logger = logging.getLogger(__name__)


class ClassificationMicroService(BaseMicroService):
    """
    Microservice for classifying emails
    
    - Reads email data from database
    - Classifies using AI
    - Returns results without writing to database
    """
    
    def __init__(self, email_classifier: EmailClassifier):
        """
        Initialize classification microservice
        
        Args:
            email_classifier: Initialized email classifier instance
        """
        super().__init__()
        self.email_classifier = email_classifier
    
    def classify_emails(self, email_ids: List[str], batch_size: int = 20) -> Dict:
        """
        Classify specified emails
        
        Args:
            email_ids: List of email IDs to classify
            batch_size: Number of emails to classify in one AI call
            
        Returns:
            {
                'classifications': [
                    {
                        'email_id': str,
                        'classification': str,
                        'confidence': float  # For future two-stage classification
                    }
                ],
                'cost_info': {
                    'input_tokens': int,
                    'output_tokens': int,
                    'total_tokens': int,
                    'estimated_cost_usd': float
                },
                'batches_processed': int,
                'errors': List[Dict]  # Any emails that failed
            }
        """
        self.log_operation('classify_emails', {
            'email_count': len(email_ids),
            'batch_size': batch_size
        })
        
        # Get emails from database
        emails_data = self._get_emails_data(email_ids)
        
        if not emails_data:
            logger.warning("No emails found for classification")
            return {
                'classifications': [],
                'cost_info': None,
                'batches_processed': 0,
                'errors': []
            }
        
        # Process in batches
        all_classifications = []
        total_cost_info = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'estimated_cost_usd': 0.0
        }
        errors = []
        batches_processed = 0
        
        for i in range(0, len(emails_data), batch_size):
            batch = emails_data[i:i + batch_size]
            batches_processed += 1
            
            try:
                # Classify batch using existing logic
                result = self.email_classifier.classify_batch(batch)
                
                # Add classifications
                all_classifications.extend(result['classifications'])
                
                # Aggregate cost info
                if result.get('cost_info'):
                    cost_info = result['cost_info']
                    total_cost_info['input_tokens'] += cost_info.get('input_tokens', 0)
                    total_cost_info['output_tokens'] += cost_info.get('output_tokens', 0)
                    total_cost_info['total_tokens'] += cost_info.get('total_tokens', 0)
                    total_cost_info['estimated_cost_usd'] += cost_info.get('estimated_cost_usd', 0.0)
                
            except Exception as e:
                logger.error(f"Failed to classify batch {batches_processed}: {e}")
                # Add failed emails to errors
                for email in batch:
                    errors.append({
                        'email_id': email['email_id'],
                        'error': str(e)
                    })
        
        logger.info(f"Classification complete: {len(all_classifications)} classified, {len(errors)} errors")
        
        return {
            'classifications': all_classifications,
            'cost_info': total_cost_info,
            'batches_processed': batches_processed,
            'errors': errors
        }
    
    @BaseMicroService.with_db
    def _get_emails_data(self, db, email_ids: List[str]) -> List[Dict]:
        """
        Get email data from database
        
        Args:
            db: Database session (injected by decorator)
            email_ids: List of email IDs
            
        Returns:
            List of email data dictionaries
        """
        emails = db.query(Email).filter(
            Email.email_id.in_(email_ids)
        ).all()
        
        # Convert to format expected by classifier
        emails_data = []
        for email in emails:
            emails_data.append({
                'email_id': email.email_id,
                'subject': email.subject or '',
                'from': email.sender or '',
                'labels': email.labels or '[]'
            })
        
        return emails_data
    
    @BaseMicroService.with_db
    def get_unclassified_emails(self, db, limit: Optional[int] = None) -> List[str]:
        """
        Get IDs of unclassified emails
        
        Useful for finding emails that need classification
        
        Args:
            db: Database session (injected by decorator)
            limit: Maximum number of IDs to return
            
        Returns:
            List of email IDs
        """
        query = db.query(Email.email_id).filter(
            Email.classification == 'unclassified'
        )
        
        if limit:
            query = query.limit(limit)
        
        emails = query.all()
        return [email[0] for email in emails]