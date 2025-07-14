#!/usr/bin/env python3
"""
Check booking extraction status counts
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent
from backend.constants import TRAVEL_CATEGORIES
from sqlalchemy import func

def check_booking_extraction_counts():
    """Check booking extraction status distribution"""
    db = SessionLocal()
    try:
        # Get counts by booking extraction status
        status_counts = db.query(
            EmailContent.booking_extraction_status, 
            func.count(EmailContent.email_id)
        ).group_by(EmailContent.booking_extraction_status).all()
        
        print("=== Booking Extraction Status Distribution ===")
        total = 0
        for status, count in status_counts:
            print(f"{status}: {count}")
            total += count
        print(f"Total: {total}")
        
        # Get travel emails that should have booking extraction
        
        # Count travel emails with different statuses
        travel_with_pending = db.query(Email).join(EmailContent).filter(
            Email.classification.in_(TRAVEL_CATEGORIES),
            EmailContent.booking_extraction_status == 'pending'
        ).count()
        
        travel_with_completed = db.query(Email).join(EmailContent).filter(
            Email.classification.in_(TRAVEL_CATEGORIES),
            EmailContent.booking_extraction_status == 'completed'
        ).count()
        
        travel_with_no_booking = db.query(Email).join(EmailContent).filter(
            Email.classification.in_(TRAVEL_CATEGORIES),
            EmailContent.booking_extraction_status == 'no_booking'
        ).count()
        
        travel_with_failed = db.query(Email).join(EmailContent).filter(
            Email.classification.in_(TRAVEL_CATEGORIES),
            EmailContent.booking_extraction_status == 'failed'
        ).count()
        
        print("\n=== Travel Emails Booking Extraction Status ===")
        print(f"Pending: {travel_with_pending}")
        print(f"Completed: {travel_with_completed}")
        print(f"No Booking: {travel_with_no_booking}")
        print(f"Failed: {travel_with_failed}")
        print(f"Total Travel Emails: {travel_with_pending + travel_with_completed + travel_with_no_booking + travel_with_failed}")
        
        # Check for emails that might need booking extraction
        # (travel emails with completed content extraction)
        eligible_for_extraction = db.query(Email).join(EmailContent).filter(
            Email.classification.in_(TRAVEL_CATEGORIES),
            EmailContent.extraction_status == 'completed'
        ).count()
        
        print(f"\n=== Eligible for Booking Extraction ===")
        print(f"Travel emails with completed content extraction: {eligible_for_extraction}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_booking_extraction_counts()