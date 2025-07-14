#!/usr/bin/env python3
"""
Analyze pending emails in detail
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent
from backend.constants import TRAVEL_CATEGORIES
from sqlalchemy import func

def analyze_pending_emails():
    """Analyze pending emails by classification"""
    db = SessionLocal()
    try:
        # Get all pending booking extraction emails
        pending_emails = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            EmailContent.booking_extraction_status == 'pending'
        ).all()
        
        print(f"=== Total Pending Emails: {len(pending_emails)} ===\n")
        
        # Group by classification
        classification_counts = {}
        for email, content in pending_emails:
            classification = email.classification or 'None'
            if classification not in classification_counts:
                classification_counts[classification] = []
            classification_counts[classification].append(email)
        
        # Sort by count
        sorted_classifications = sorted(classification_counts.items(), key=lambda x: len(x[1]), reverse=True)
        
        print("=== Pending Emails by Classification ===")
        for classification, emails in sorted_classifications:
            print(f"\n{classification}: {len(emails)} emails")
            # Show first 3 examples
            for email in emails[:3]:
                print(f"  - {email.email_id}: {email.subject[:60]}...")
        
        # Check travel categories
        
        # Count pending travel emails
        pending_travel = db.query(Email).join(EmailContent).filter(
            Email.classification.in_(TRAVEL_CATEGORIES),
            EmailContent.booking_extraction_status == 'pending'
        ).count()
        
        print(f"\n=== Pending Travel Emails: {pending_travel} ===")
        
        # Check content extraction status for pending booking extraction
        print("\n=== Content Extraction Status of Pending Booking Emails ===")
        content_status_counts = db.query(
            EmailContent.extraction_status,
            func.count(EmailContent.email_id)
        ).filter(
            EmailContent.booking_extraction_status == 'pending'
        ).group_by(EmailContent.extraction_status).all()
        
        for status, count in content_status_counts:
            print(f"{status}: {count}")
            
    finally:
        db.close()

if __name__ == "__main__":
    analyze_pending_emails()