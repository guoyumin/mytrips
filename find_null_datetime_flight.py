#!/usr/bin/env python3
"""
Find emails with flight bookings that have null datetime
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent, TransportSegment
from sqlalchemy import and_, or_
import json

def find_flights_with_null_datetime():
    """Find flight bookings with null datetime"""
    db = SessionLocal()
    try:
        # Find all transport segments with null datetime
        null_datetime_segments = db.query(TransportSegment).filter(
            or_(
                TransportSegment.departure_datetime == None,
                TransportSegment.arrival_datetime == None
            )
        ).all()
        
        print(f"=== Found {len(null_datetime_segments)} transport segments with null datetime ===\n")
        
        for segment in null_datetime_segments:
            print(f"Segment ID: {segment.id}")
            print(f"Type: {segment.segment_type}")
            print(f"Route: {segment.departure_location} -> {segment.arrival_location}")
            print(f"Departure: {segment.departure_datetime}")
            print(f"Arrival: {segment.arrival_datetime}")
            print(f"Status: {segment.status}")
            print(f"Trip ID: {segment.trip_id}")
            
            # Get related emails
            related_emails = segment.emails
            print(f"\nRelated emails ({len(related_emails)}):")
            for email in related_emails:
                print(f"  - {email.email_id}: {email.subject}")
                print(f"    From: {email.sender}")
                print(f"    Date: {email.date}")
            print("-" * 80)
            
        # Also check EmailContent for booking data with null datetime
        print("\n=== Checking EmailContent for bookings with null datetime ===\n")
        
        # Get all emails with completed booking extraction
        completed_bookings = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            EmailContent.booking_extraction_status == 'completed'
        ).all()
        
        for email, content in completed_bookings:
            if content.extracted_booking_info:
                try:
                    booking_data = json.loads(content.extracted_booking_info)
                    
                    # Check transport_segments
                    if 'transport_segments' in booking_data:
                        for seg in booking_data['transport_segments']:
                            if (seg.get('segment_type') == 'flight' and 
                                (seg.get('departure_datetime') is None or 
                                 seg.get('arrival_datetime') is None)):
                                print(f"Email ID: {email.email_id}")
                                print(f"Subject: {email.subject}")
                                print(f"From: {email.sender}")
                                print(f"Date: {email.date}")
                                print(f"Classification: {email.classification}")
                                print(f"\nFlight segment with null datetime:")
                                print(f"  Route: {seg.get('departure_location')} -> {seg.get('arrival_location')}")
                                print(f"  Departure: {seg.get('departure_datetime')}")
                                print(f"  Arrival: {seg.get('arrival_datetime')}")
                                print(f"  Carrier: {seg.get('carrier_name')}")
                                print("-" * 80)
                                
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"Error processing {email.email_id}: {e}")
                    
    finally:
        db.close()

if __name__ == "__main__":
    find_flights_with_null_datetime()