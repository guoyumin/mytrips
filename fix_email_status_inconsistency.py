#!/usr/bin/env python3
"""
Fix email status inconsistency - migrate existing data to use correct statuses
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent
from backend.constants import TRAVEL_CATEGORIES
from sqlalchemy import func

def fix_email_status_inconsistency():
    """Fix status inconsistency for non-travel emails"""
    db = SessionLocal()
    try:
        print("=== Fixing Email Status Inconsistency ===\n")
        
        # Get non-travel email IDs first
        non_travel_email_ids = [row[0] for row in db.query(Email.email_id).filter(
            ~Email.classification.in_(TRAVEL_CATEGORIES)
        ).all()]
        
        # 1. Fix extraction_status for non-travel emails
        print("1. Updating extraction_status for non-travel emails...")
        extraction_updated = db.query(EmailContent).filter(
            EmailContent.email_id.in_(non_travel_email_ids),
            EmailContent.extraction_status.in_(['pending', 'completed', 'failed'])
        ).update({
            'extraction_status': 'not_required',
            'extraction_error': None
        }, synchronize_session=False)
        
        print(f"   Updated {extraction_updated} non-travel emails to extraction_status='not_required'")
        
        # 2. Fix booking_extraction_status for non-travel emails
        print("\n2. Updating booking_extraction_status for non-travel emails...")
        booking_updated = db.query(EmailContent).filter(
            EmailContent.email_id.in_(non_travel_email_ids),
            EmailContent.booking_extraction_status == 'pending'
        ).update({
            'booking_extraction_status': 'not_travel',
            'booking_extraction_error': 'Not a travel email'
        }, synchronize_session=False)
        
        print(f"   Updated {booking_updated} non-travel emails to booking_extraction_status='not_travel'")
        
        # Commit all changes
        db.commit()
        
        # 3. Verify the fix
        print("\n3. Verifying the fix...")
        
        # Count non-travel emails with incorrect statuses
        incorrect_extraction = db.query(EmailContent).join(Email).filter(
            ~Email.classification.in_(travel_categories),
            EmailContent.extraction_status != 'not_required'
        ).count()
        
        incorrect_booking = db.query(EmailContent).join(Email).filter(
            ~Email.classification.in_(travel_categories),
            EmailContent.booking_extraction_status.in_(['pending', 'extracting', 'completed', 'failed', 'no_booking'])
        ).count()
        
        print(f"   Non-travel emails with incorrect extraction_status: {incorrect_extraction}")
        print(f"   Non-travel emails with incorrect booking_extraction_status: {incorrect_booking}")
        
        if incorrect_extraction == 0 and incorrect_booking == 0:
            print("\n✅ All non-travel emails have been fixed!")
        else:
            print("\n⚠️  Some emails still have incorrect status. Please investigate.")
        
        # 4. Show updated status distribution
        print("\n4. Updated Status Distribution:")
        
        # Travel emails status
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
        
        # Non-travel emails status
        print("\nNon-Travel Emails:")
        non_travel_statuses = db.query(
            EmailContent.extraction_status,
            EmailContent.booking_extraction_status,
            func.count(EmailContent.email_id)
        ).join(Email).filter(
            ~Email.classification.in_(travel_categories)
        ).group_by(
            EmailContent.extraction_status,
            EmailContent.booking_extraction_status
        ).all()
        
        for ext_status, book_status, count in non_travel_statuses:
            print(f"  extraction: {ext_status}, booking: {book_status} => {count} emails")
        
        print("\n=== Migration Complete ===")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    fix_email_status_inconsistency()