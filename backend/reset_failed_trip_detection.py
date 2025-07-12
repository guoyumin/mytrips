#!/usr/bin/env python
"""Reset failed trip detection emails to pending status"""
import sys
from sqlalchemy import func
from backend.database.config import SessionLocal
from backend.database.models import EmailContent
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def reset_failed_emails():
    """Reset all failed trip detection emails to pending status"""
    db = SessionLocal()
    try:
        # First, let's see how many failed emails we have
        failed_count = db.query(EmailContent).filter(
            EmailContent.trip_detection_status == 'failed'
        ).count()
        
        logger.info(f"Found {failed_count} emails with failed trip detection status")
        
        if failed_count == 0:
            logger.info("No failed emails to reset")
            return
        
        # Get some sample failed emails to understand the errors
        sample_failed = db.query(EmailContent).filter(
            EmailContent.trip_detection_status == 'failed'
        ).limit(10).all()
        
        logger.info("\nSample of failed emails and their errors:")
        for email in sample_failed:
            logger.info(f"Email ID: {email.email_id}")
            logger.info(f"  Error: {email.trip_detection_error}")
            logger.info("  ---")
        
        # Auto-confirm for non-interactive execution
        logger.info(f"\nResetting all {failed_count} failed emails to pending...")
        
        # Reset all failed emails to pending
        updated = db.query(EmailContent).filter(
            EmailContent.trip_detection_status == 'failed'
        ).update({
            'trip_detection_status': 'pending',
            'trip_detection_error': None,
            'trip_detection_processed_at': None
        })
        
        db.commit()
        logger.info(f"Successfully reset {updated} emails from failed to pending status")
        
        # Also check for emails that might have incomplete booking information marked as failed
        incomplete_count = db.query(EmailContent).filter(
            EmailContent.trip_detection_error.like('%Incomplete booking information%')
        ).count()
        
        if incomplete_count > 0:
            logger.warning(f"\nNote: {incomplete_count} emails were marked as having incomplete booking information.")
            logger.warning("These may fail again if the booking information is truly incomplete.")
        
    except Exception as e:
        logger.error(f"Error resetting failed emails: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def analyze_booking_status():
    """Analyze booking extraction status to understand potential issues"""
    db = SessionLocal()
    try:
        # Check booking extraction status distribution
        booking_status_counts = db.query(
            EmailContent.booking_extraction_status,
            func.count(EmailContent.email_id).label('count')
        ).group_by(EmailContent.booking_extraction_status).all()
        
        logger.info("\nBooking extraction status distribution:")
        for status, count in booking_status_counts:
            logger.info(f"  {status}: {count}")
        
        # Check emails with completed booking extraction but failed trip detection
        problematic = db.query(EmailContent).filter(
            EmailContent.booking_extraction_status == 'completed',
            EmailContent.trip_detection_status == 'failed'
        ).count()
        
        logger.info(f"\nEmails with completed booking extraction but failed trip detection: {problematic}")
        
    except Exception as e:
        logger.error(f"Error analyzing booking status: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Starting failed trip detection reset process...")
    
    # First analyze the current state
    analyze_booking_status()
    
    # Then reset failed emails
    reset_failed_emails()
    
    logger.info("\nProcess completed!")