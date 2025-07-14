#!/usr/bin/env python3
"""
Check current trip detection status
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent
from sqlalchemy import and_, or_, func

def check_trip_detection_status():
    """Check current trip detection status distribution"""
    db = SessionLocal()
    try:
        # Get status counts
        status_counts = db.query(
            EmailContent.trip_detection_status, 
            func.count(EmailContent.email_id)
        ).group_by(EmailContent.trip_detection_status).all()
        
        print("=== Trip Detection Status Distribution ===")
        for status, count in status_counts:
            print(f"{status}: {count}")
        
        # Get failed emails with errors
        failed_with_errors = db.query(
            Email, EmailContent
        ).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            EmailContent.trip_detection_status == 'failed'
        ).all()
        
        print(f"\n=== Failed Emails ({len(failed_with_errors)}) ===")
        for email, content in failed_with_errors[:10]:  # Show first 10
            print(f"\nEmail ID: {email.email_id}")
            print(f"Subject: {email.subject[:80]}...")
            print(f"Date: {email.date}")
            print(f"Classification: {email.classification}")
            print(f"Error: {content.trip_detection_error}")
            
        # Check specific email
        print("\n=== Checking 1976d9f2693af463 ===")
        specific = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(Email.email_id == '1976d9f2693af463').first()
        
        if specific:
            email, content = specific
            print(f"Subject: {email.subject}")
            print(f"Classification: {email.classification}")
            print(f"Booking Extraction Status: {content.booking_extraction_status}")
            print(f"Trip Detection Status: {content.trip_detection_status}")
            print(f"Trip Detection Error: {content.trip_detection_error}")
        else:
            print("Email not found!")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_trip_detection_status()