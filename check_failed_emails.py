#!/usr/bin/env python3
"""
Script to check failed trip detection emails
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent, TransportSegment, Accommodation, TourActivity, Cruise
from sqlalchemy import and_
import json

def check_specific_email(email_id):
    """Check a specific email's status and content"""
    db = SessionLocal()
    try:
        # Get email info
        email = db.query(Email).filter(Email.email_id == email_id).first()
        if not email:
            print(f"Email {email_id} not found in emails table")
            return
            
        print(f"\n=== Email: {email_id} ===")
        print(f"Subject: {email.subject}")
        print(f"From: {email.sender}")
        print(f"Date: {email.date}")
        print(f"Classification: {email.classification}")
        
        # Get email content
        content = db.query(EmailContent).filter(EmailContent.email_id == email_id).first()
        if content:
            print(f"\nEmail Content Status:")
            print(f"- Extraction Status: {content.extraction_status}")
            print(f"- Booking Extraction Status: {content.booking_extraction_status}")
            print(f"- Trip Detection Status: {content.trip_detection_status}")
            if content.trip_detection_error:
                print(f"- Trip Detection Error: {content.trip_detection_error}")
        
        # Check if email has any bookings in the actual booking tables
        transports = db.query(TransportSegment).join(TransportSegment.emails).filter(Email.email_id == email_id).all()
        accommodations = db.query(Accommodation).join(Accommodation.emails).filter(Email.email_id == email_id).all()
        tours = db.query(TourActivity).join(TourActivity.emails).filter(Email.email_id == email_id).all()
        cruises = db.query(Cruise).join(Cruise.emails).filter(Email.email_id == email_id).all()
        
        total_bookings = len(transports) + len(accommodations) + len(tours) + len(cruises)
        if total_bookings > 0:
            print(f"\nBookings found:")
            if transports:
                print(f"- Transport segments: {len(transports)}")
                for t in transports:
                    print(f"  {t.segment_type}: {t.departure_location} -> {t.arrival_location} on {t.departure_datetime}")
            if accommodations:
                print(f"- Accommodations: {len(accommodations)}")
                for a in accommodations:
                    print(f"  {a.property_name} in {a.city}, {a.check_in_date} to {a.check_out_date}")
            if tours:
                print(f"- Tours: {len(tours)}")
                for t in tours:
                    print(f"  {t.activity_name} in {t.city} on {t.start_datetime}")
            if cruises:
                print(f"- Cruises: {len(cruises)}")
                for c in cruises:
                    print(f"  {c.cruise_line} - {c.ship_name}")
        else:
            print("\nNo bookings found for this email")
                            
    finally:
        db.close()

def check_all_failed_emails():
    """Get all emails that failed trip detection"""
    db = SessionLocal()
    try:
        # Query for failed trip detection
        failed_emails = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            EmailContent.trip_detection_status == 'failed'
        ).all()
        
        print(f"\n=== Failed Trip Detection Emails ===")
        print(f"Total failed: {len(failed_emails)}")
        
        # Group by error type
        error_types = {}
        for email, content in failed_emails:
            error = content.trip_detection_error or "Unknown error"
            if error not in error_types:
                error_types[error] = []
            error_types[error].append({
                'email_id': email.email_id,
                'subject': email.subject,
                'date': email.date,
                'classification': email.classification
            })
        
        print("\nErrors grouped by type:")
        for error, emails in error_types.items():
            print(f"\n{error}: {len(emails)} emails")
            # Show first few examples
            for email in emails[:3]:
                print(f"  - {email['email_id']}: {email['subject'][:60]}...")
                
    finally:
        db.close()

def check_booking_vs_trip_detection():
    """Check emails with successful booking extraction but failed trip detection"""
    db = SessionLocal()
    try:
        # Query for this specific case
        problematic = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            and_(
                EmailContent.booking_extraction_status == 'completed',
                EmailContent.trip_detection_status == 'failed'
            )
        ).all()
        
        print(f"\n=== Booking Success but Trip Detection Failed ===")
        print(f"Total: {len(problematic)} emails")
        
        # Check first few in detail
        for email, content in problematic[:5]:
            print(f"\n- Email: {email.email_id}")
            print(f"  Subject: {email.subject[:80]}...")
            
            # Check if error details exist
            if content.trip_detection_error:
                print(f"  Error: {content.trip_detection_error}")
            print(f"  Booking extraction status: {content.booking_extraction_status}")
                
    finally:
        db.close()

if __name__ == "__main__":
    # Check specific email
    print("Checking specific email: 1976d9f2693af463")
    check_specific_email("1976d9f2693af463")
    
    # Check all failed emails
    check_all_failed_emails()
    
    # Check booking vs trip detection mismatches
    check_booking_vs_trip_detection()