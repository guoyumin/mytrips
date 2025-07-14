#!/usr/bin/env python3
"""
Analyze booking extraction status inconsistency
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent
from backend.constants import TRAVEL_CATEGORIES
from sqlalchemy import func
import json

def analyze_booking_status_inconsistency():
    """Analyze emails with inconsistent booking extraction status"""
    db = SessionLocal()
    try:
        
        # Find non-travel emails with pending booking extraction status
        non_travel_with_pending = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            ~Email.classification.in_(TRAVEL_CATEGORIES),
            EmailContent.booking_extraction_status == 'pending'
        ).all()
        
        print(f"=== Non-Travel Emails with 'pending' Booking Extraction Status ===")
        print(f"Total: {len(non_travel_with_pending)}\n")
        
        # Group by classification
        classification_counts = {}
        for email, content in non_travel_with_pending:
            classification = email.classification or 'None'
            if classification not in classification_counts:
                classification_counts[classification] = []
            classification_counts[classification].append((email, content))
        
        # Sort by count
        sorted_classifications = sorted(classification_counts.items(), key=lambda x: len(x[1]), reverse=True)
        
        print("Breakdown by Classification:")
        for classification, emails_list in sorted_classifications:
            print(f"\n{classification}: {len(emails_list)} emails")
            
            # Show examples
            for email, content in emails_list[:3]:
                print(f"  - Email ID: {email.email_id}")
                print(f"    Subject: {email.subject[:60]}...")
                print(f"    Content Status: {content.extraction_status}")
                print(f"    Booking Status: {content.booking_extraction_status}")
                
                # Check if it has extracted booking info
                if content.extracted_booking_info:
                    try:
                        booking_info = json.loads(content.extracted_booking_info)
                        print(f"    Has Booking Info: Yes (is_travel: {booking_info.get('is_travel', 'N/A')})")
                    except:
                        print(f"    Has Booking Info: Invalid JSON")
                else:
                    print(f"    Has Booking Info: No")
        
        print("\n=== Summary ===")
        print("These non-travel emails should have booking_extraction_status = 'not_travel'")
        print("instead of 'pending' to avoid unnecessary reprocessing.")
        
        # Check if any have been processed before
        processed_count = 0
        for email, content in non_travel_with_pending:
            if content.extracted_booking_info:
                processed_count += 1
        
        print(f"\nAlready processed but still marked as pending: {processed_count}")
        print(f"Never processed: {len(non_travel_with_pending) - processed_count}")
        
    finally:
        db.close()

if __name__ == "__main__":
    analyze_booking_status_inconsistency()