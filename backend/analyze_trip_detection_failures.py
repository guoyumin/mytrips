#!/usr/bin/env python
"""Analyze trip detection failures in detail"""
import sys
import json
from collections import defaultdict
from sqlalchemy import and_
from backend.database.config import SessionLocal
from backend.database.models import Email, EmailContent
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_failures():
    """Analyze trip detection failures in detail"""
    db = SessionLocal()
    try:
        # Get all failed emails with their booking info
        failed_emails = db.query(Email, EmailContent).join(EmailContent).filter(
            EmailContent.trip_detection_status == 'failed'
        ).all()
        
        logger.info(f"Total failed emails: {len(failed_emails)}")
        
        # Group failures by error type
        error_groups = defaultdict(list)
        booking_type_failures = defaultdict(int)
        
        for email, content in failed_emails:
            error = content.trip_detection_error or "Unknown error"
            error_groups[error].append(email.email_id)
            
            # Try to get booking type
            if content.extracted_booking_info:
                try:
                    booking_info = json.loads(content.extracted_booking_info)
                    booking_type = booking_info.get('booking_type', 'unknown')
                    booking_type_failures[booking_type] += 1
                except:
                    booking_type_failures['parse_error'] += 1
            else:
                booking_type_failures['no_booking_info'] += 1
        
        # Display error groups
        logger.info("\nFailures grouped by error message:")
        for error, email_ids in error_groups.items():
            logger.info(f"\n{error}: {len(email_ids)} emails")
            # Show first 3 email IDs as examples
            for email_id in email_ids[:3]:
                logger.info(f"  - {email_id}")
            if len(email_ids) > 3:
                logger.info(f"  ... and {len(email_ids) - 3} more")
        
        # Display failures by booking type
        logger.info("\nFailures by booking type:")
        for booking_type, count in booking_type_failures.items():
            logger.info(f"  {booking_type}: {count}")
        
        # Analyze specific case: Incomplete booking information
        incomplete_emails = db.query(Email, EmailContent).join(EmailContent).filter(
            EmailContent.trip_detection_error.like('%Incomplete booking information%')
        ).limit(5).all()
        
        logger.info("\nDetailed analysis of 'Incomplete booking information' errors:")
        for email, content in incomplete_emails:
            logger.info(f"\nEmail ID: {email.email_id}")
            logger.info(f"Subject: {email.subject[:80]}...")
            logger.info(f"Classification: {email.classification}")
            
            if content.extracted_booking_info:
                try:
                    booking_info = json.loads(content.extracted_booking_info)
                    booking_type = booking_info.get('booking_type', 'unknown')
                    logger.info(f"Booking type: {booking_type}")
                    
                    # Show what fields are present
                    logger.info("Fields present in booking info:")
                    for key, value in booking_info.items():
                        if value is not None and value != "" and value != []:
                            value_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                            logger.info(f"  - {key}: {value_str}")
                except Exception as e:
                    logger.error(f"  Failed to parse booking info: {e}")
        
        # Check for potential issues with the completeness check
        logger.info("\n\nChecking a sample email that should be complete...")
        
        # Get a flight booking that failed
        sample_flight = db.query(Email, EmailContent).join(EmailContent).filter(
            EmailContent.trip_detection_error.like('%Incomplete booking information%'),
            Email.classification == 'flight'
        ).first()
        
        if sample_flight:
            email, content = sample_flight
            logger.info(f"\nSample flight email: {email.email_id}")
            logger.info(f"Subject: {email.subject}")
            
            if content.extracted_booking_info:
                try:
                    booking_info = json.loads(content.extracted_booking_info)
                    logger.info(f"\nFull booking info:")
                    logger.info(json.dumps(booking_info, indent=2))
                except Exception as e:
                    logger.error(f"Failed to parse booking info: {e}")
        
    except Exception as e:
        logger.error(f"Error analyzing failures: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    analyze_failures()