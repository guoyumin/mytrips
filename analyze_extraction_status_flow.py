#!/usr/bin/env python3
"""
Analyze the flow of extraction status and booking extraction status
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent
from backend.constants import TRAVEL_CATEGORIES
from sqlalchemy import func

def analyze_extraction_status_flow():
    """Analyze how extraction status and booking extraction status relate"""
    db = SessionLocal()
    try:
        
        print("=== Extraction Status Flow Analysis ===\n")
        
        # 1. Count emails by classification
        print("1. Email Classification Distribution:")
        classification_counts = db.query(
            Email.classification,
            func.count(Email.email_id)
        ).group_by(Email.classification).all()
        
        travel_count = 0
        non_travel_count = 0
        for classification, count in classification_counts:
            if classification in TRAVEL_CATEGORIES:
                travel_count += count
                print(f"  {classification}: {count} (travel)")
            else:
                non_travel_count += count
                print(f"  {classification}: {count} (non-travel)")
        
        print(f"\nTotal Travel Emails: {travel_count}")
        print(f"Total Non-Travel Emails: {non_travel_count}")
        
        # 2. Check EmailContent status distribution
        print("\n2. EmailContent Status Distribution:")
        
        # For travel emails
        print("\nTravel Emails:")
        travel_statuses = db.query(
            EmailContent.extraction_status,
            EmailContent.booking_extraction_status,
            func.count(EmailContent.email_id)
        ).join(Email).filter(
            Email.classification.in_(TRAVEL_CATEGORIES)
        ).group_by(
            EmailContent.extraction_status,
            EmailContent.booking_extraction_status
        ).all()
        
        for ext_status, book_status, count in travel_statuses:
            print(f"  extraction: {ext_status}, booking: {book_status} => {count} emails")
        
        # For non-travel emails
        print("\nNon-Travel Emails:")
        non_travel_statuses = db.query(
            EmailContent.extraction_status,
            EmailContent.booking_extraction_status,
            func.count(EmailContent.email_id)
        ).join(Email).filter(
            ~Email.classification.in_(TRAVEL_CATEGORIES)
        ).group_by(
            EmailContent.extraction_status,
            EmailContent.booking_extraction_status
        ).all()
        
        for ext_status, book_status, count in non_travel_statuses:
            print(f"  extraction: {ext_status}, booking: {book_status} => {count} emails")
        
        # 3. Check which non-travel emails have EmailContent records
        print("\n3. Non-Travel Emails with EmailContent Records:")
        non_travel_with_content = db.query(Email).join(EmailContent).filter(
            ~Email.classification.in_(TRAVEL_CATEGORIES)
        ).count()
        
        non_travel_without_content = db.query(Email).filter(
            ~Email.classification.in_(TRAVEL_CATEGORIES),
            ~Email.email_id.in_(
                db.query(EmailContent.email_id)
            )
        ).count()
        
        print(f"  With EmailContent: {non_travel_with_content}")
        print(f"  Without EmailContent: {non_travel_without_content}")
        
        # 4. Check how non-travel emails got EmailContent records
        print("\n4. Why Non-Travel Emails Have EmailContent Records:")
        print("(Likely from reset operations that create EmailContent for all emails)")
        
        # Find non-travel emails with extracted content
        non_travel_extracted = db.query(Email).join(EmailContent).filter(
            ~Email.classification.in_(TRAVEL_CATEGORIES),
            EmailContent.extraction_status == 'completed'
        ).count()
        
        print(f"  Non-travel emails with completed extraction: {non_travel_extracted}")
        print("  This suggests they were processed before being classified as non-travel")
        
    finally:
        db.close()

if __name__ == "__main__":
    analyze_extraction_status_flow()