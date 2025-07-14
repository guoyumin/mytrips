#!/usr/bin/env python3
"""
Find Oslo related bookings
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent
from sqlalchemy import and_, or_
import json

def find_oslo_bookings():
    """Find Oslo related bookings in EmailContent"""
    db = SessionLocal()
    try:
        # Get all Oslo-related emails with completed booking extraction
        oslo_emails = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            and_(
                Email.subject.ilike('%oslo%'),
                EmailContent.booking_extraction_status == 'completed'
            )
        ).all()
        
        print(f"=== Found {len(oslo_emails)} Oslo emails with completed booking extraction ===\n")
        
        for email, content in oslo_emails:
            print(f"Email ID: {email.email_id}")
            print(f"Subject: {email.subject}")
            print(f"From: {email.sender}")
            print(f"Date: {email.date}")
            print(f"Classification: {email.classification}")
            
            if content.extracted_booking_info:
                try:
                    booking_data = json.loads(content.extracted_booking_info)
                    
                    # Check if this is a booking or non-booking
                    if 'booking_type' in booking_data:
                        print(f"Booking Type: {booking_data['booking_type']}")
                    
                    # Check transport_segments
                    if 'transport_segments' in booking_data:
                        print(f"\nTransport Segments ({len(booking_data['transport_segments'])}):")
                        for i, seg in enumerate(booking_data['transport_segments']):
                            print(f"  Segment {i}:")
                            print(f"    Type: {seg.get('segment_type')}")
                            print(f"    Route: {seg.get('departure_location')} -> {seg.get('arrival_location')}")
                            print(f"    Departure: {seg.get('departure_datetime')}")
                            print(f"    Arrival: {seg.get('arrival_datetime')}")
                            print(f"    Carrier: {seg.get('carrier_name')}")
                            
                    # Check accommodations
                    if 'accommodations' in booking_data:
                        print(f"\nAccommodations ({len(booking_data['accommodations'])}):")
                        for i, acc in enumerate(booking_data['accommodations']):
                            print(f"  Accommodation {i}:")
                            print(f"    Name: {acc.get('property_name')}")
                            print(f"    City: {acc.get('city')}")
                            print(f"    Check-in: {acc.get('check_in_date')}")
                            print(f"    Check-out: {acc.get('check_out_date')}")
                            
                    # Show the full JSON for debugging
                    print(f"\nFull booking data:")
                    print(json.dumps(booking_data, indent=2)[:1000] + "...")
                    
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}")
                except Exception as e:
                    print(f"Error: {e}")
            else:
                print("No extracted booking info")
                
            print("-" * 80)
            
        # Also search for flights TO Oslo (not in subject)
        print("\n=== Searching for flights TO Oslo/Gardermoen ===\n")
        
        completed_bookings = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            EmailContent.booking_extraction_status == 'completed'
        ).all()
        
        for email, content in completed_bookings:
            if content.extracted_booking_info:
                try:
                    booking_data = json.loads(content.extracted_booking_info)
                    
                    # Check transport_segments for Oslo destinations
                    if 'transport_segments' in booking_data:
                        for seg in booking_data['transport_segments']:
                            arrival = seg.get('arrival_location', '')
                            if arrival and ('oslo' in arrival.lower() or 'gardermoen' in arrival.lower()):
                                print(f"Email ID: {email.email_id}")
                                print(f"Subject: {email.subject[:80]}...")
                                print(f"Flight to Oslo/Gardermoen:")
                                print(f"  Route: {seg.get('departure_location')} -> {arrival}")
                                print(f"  Departure: {seg.get('departure_datetime')}")
                                print(f"  Arrival: {seg.get('arrival_datetime')}")
                                print("-" * 40)
                                
                except:
                    pass
                    
    finally:
        db.close()

if __name__ == "__main__":
    find_oslo_bookings()