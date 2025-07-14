#!/usr/bin/env python3
"""
Check Oslo trip related emails
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent, TransportSegment, Accommodation
from sqlalchemy import or_, and_
import json

def find_oslo_emails():
    """Find all emails related to Oslo"""
    db = SessionLocal()
    try:
        # Search for Oslo in subject or content
        oslo_emails = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            Email.subject.ilike('%oslo%')
        ).all()
        
        print(f"=== Found {len(oslo_emails)} Oslo-related emails ===\n")
        
        for email, content in oslo_emails:
            print(f"Email ID: {email.email_id}")
            print(f"Subject: {email.subject}")
            print(f"Date: {email.date}")
            print(f"Classification: {email.classification}")
            print(f"Booking Extraction Status: {content.booking_extraction_status}")
            print(f"Trip Detection Status: {content.trip_detection_status}")
            if content.trip_detection_error:
                print(f"Trip Detection Error: {content.trip_detection_error}")
            
            # Check for transport segments
            transports = db.query(TransportSegment).join(
                TransportSegment.emails
            ).filter(Email.email_id == email.email_id).all()
            
            if transports:
                print(f"Transport Segments: {len(transports)}")
                for t in transports:
                    print(f"  - {t.segment_type}: {t.departure_location} -> {t.arrival_location}")
                    print(f"    Departure: {t.departure_datetime}")
                    print(f"    Arrival: {t.arrival_datetime}")
            
            # Check for accommodations
            accommodations = db.query(Accommodation).join(
                Accommodation.emails
            ).filter(Email.email_id == email.email_id).all()
            
            if accommodations:
                print(f"Accommodations: {len(accommodations)}")
                for a in accommodations:
                    print(f"  - {a.property_name} in {a.city}")
                    print(f"    Check-in: {a.check_in_date}")
                    
            print("-" * 80)
            
    finally:
        db.close()

def check_failed_trip_logs():
    """Check logs for Oslo trip failure details"""
    print("\n=== Checking logs for Oslo trip errors ===\n")
    
    # Search for Oslo trip errors in the log
    import subprocess
    result = subprocess.run(
        ["grep", "-B10", "-A10", "Trip to Oslo", "logs/server.log"],
        capture_output=True,
        text=True
    )
    
    if result.stdout:
        lines = result.stdout.split('\n')
        # Find unique error occurrences
        seen_errors = set()
        for i, line in enumerate(lines):
            if "Trip to Oslo" in line and "ERROR" in line:
                # Get context around the error
                start = max(0, i-5)
                end = min(len(lines), i+5)
                error_context = '\n'.join(lines[start:end])
                if error_context not in seen_errors:
                    seen_errors.add(error_context)
                    print(error_context)
                    print("=" * 80)

if __name__ == "__main__":
    find_oslo_emails()
    check_failed_trip_logs()