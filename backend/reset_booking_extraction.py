#!/usr/bin/env python3
"""
Reset all email booking extraction data to re-run with normalized array format
"""
import logging
from sqlalchemy import update
from database.config import SessionLocal
from database.models import EmailContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_booking_extraction():
    """Reset all booking extraction data"""
    db = SessionLocal()
    try:
        # Count total records to reset
        total_count = db.query(EmailContent).count()
        logger.info(f"Total email content records: {total_count}")
        
        # Reset all booking extraction data
        result = db.query(EmailContent).update({
            'extracted_booking_info': None,
            'booking_extraction_status': 'pending',
            'booking_extraction_error': None
        }, synchronize_session=False)
        
        db.commit()
        logger.info(f"Successfully reset {result} email content records")
        
        # Count different statuses after reset
        pending_count = db.query(EmailContent).filter(
            EmailContent.booking_extraction_status == 'pending'
        ).count()
        
        logger.info(f"Booking extraction status after reset:")
        logger.info(f"  - Pending: {pending_count}")
        
    except Exception as e:
        logger.error(f"Error resetting booking extraction: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Starting booking extraction reset...")
    reset_booking_extraction()
    logger.info("Reset complete. You can now re-run email booking extraction.")