#!/usr/bin/env python3
"""
Test the new array format for booking extraction
"""
import json
import logging
from database.config import SessionLocal
from database.models import Email, EmailContent
from services.email_booking_extraction_service import EmailBookingExtractionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_array_format():
    """Test that the new array format is working correctly"""
    db = SessionLocal()
    service = EmailBookingExtractionService()
    
    try:
        # Find a few test emails with different booking types
        test_emails = []
        
        # Find a flight email
        flight_email = db.query(Email).join(EmailContent).filter(
            Email.classification == 'flight',
            EmailContent.extraction_status == 'completed'
        ).first()
        if flight_email:
            test_emails.append(('flight', flight_email))
            
        # Find a hotel email
        hotel_email = db.query(Email).join(EmailContent).filter(
            Email.classification == 'hotel',
            EmailContent.extraction_status == 'completed'
        ).first()
        if hotel_email:
            test_emails.append(('hotel', hotel_email))
            
        # Find a train email
        train_email = db.query(Email).join(EmailContent).filter(
            Email.classification == 'train',
            EmailContent.extraction_status == 'completed'
        ).first()
        if train_email:
            test_emails.append(('train', train_email))
        
        logger.info(f"Found {len(test_emails)} test emails")
        
        # Test extraction for each email
        for booking_type, email in test_emails:
            logger.info(f"\nTesting {booking_type} email: {email.email_id}")
            logger.info(f"Subject: {email.subject[:50]}...")
            
            # Extract booking info
            success = service._extract_single_email_booking(email, db)
            
            if success:
                # Check the extracted format
                content = email.email_content
                if content.extracted_booking_info:
                    booking_info = json.loads(content.extracted_booking_info)
                    logger.info(f"Extraction status: {content.booking_extraction_status}")
                    
                    # Verify array format
                    if booking_info.get('booking_type'):
                        logger.info(f"Booking type: {booking_info['booking_type']}")
                        
                        # Check for array fields
                        if 'transport_segments' in booking_info:
                            logger.info(f"✓ transport_segments is array: {isinstance(booking_info['transport_segments'], list)}")
                            logger.info(f"  Segments count: {len(booking_info['transport_segments'])}")
                            
                        if 'accommodations' in booking_info:
                            logger.info(f"✓ accommodations is array: {isinstance(booking_info['accommodations'], list)}")
                            logger.info(f"  Accommodations count: {len(booking_info['accommodations'])}")
                            
                        if 'activities' in booking_info:
                            logger.info(f"✓ activities is array: {isinstance(booking_info['activities'], list)}")
                            logger.info(f"  Activities count: {len(booking_info['activities'])}")
                            
                        if 'cruises' in booking_info:
                            logger.info(f"✓ cruises is array: {isinstance(booking_info['cruises'], list)}")
                            logger.info(f"  Cruises count: {len(booking_info['cruises'])}")
                        
                        # Check for old field names (should not exist)
                        old_fields = ['transport_details', 'accommodation_details', 'activity_details', 'cruise_details']
                        for field in old_fields:
                            if field in booking_info:
                                logger.warning(f"✗ Old field '{field}' still exists!")
                    else:
                        logger.info(f"Non-booking email: {booking_info.get('non_booking_type', 'unknown')}")
            else:
                logger.error(f"Failed to extract booking info")
        
        # Don't commit changes - this is just a test
        db.rollback()
        logger.info("\nTest completed (no changes saved)")
        
    except Exception as e:
        logger.error(f"Test error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Testing new array format for booking extraction...")
    test_array_format()