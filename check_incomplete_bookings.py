#!/usr/bin/env python3
"""
Check for bookings with incomplete datetime information
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent
import json

def check_incomplete_bookings():
    """Find bookings with incomplete datetime"""
    db = SessionLocal()
    try:
        # Get all Oslo and Gardermoen related emails
        oslo_emails = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            EmailContent.booking_extraction_status == 'completed'
        ).all()
        
        print("=== Checking for incomplete flight bookings ===\n")
        
        incomplete_flights = []
        
        for email, content in oslo_emails:
            # Check if subject or content mentions Oslo, Gardermoen, or is related to the trip dates
            if any(keyword in email.subject.lower() for keyword in ['oslo', 'gardermoen', 'june', 'jun']):
                if content.extracted_booking_info:
                    try:
                        booking_data = json.loads(content.extracted_booking_info)
                        
                        # Check transport_segments
                        if 'transport_segments' in booking_data:
                            for seg in booking_data['transport_segments']:
                                # Check if this segment has incomplete datetime
                                dep_dt = seg.get('departure_datetime')
                                arr_dt = seg.get('arrival_datetime')
                                
                                # Check if datetime exists but is incomplete (only date, no time)
                                if dep_dt and 'T00:00:00' in str(dep_dt) and not arr_dt:
                                    print(f"Found incomplete flight booking:")
                                    print(f"Email ID: {email.email_id}")
                                    print(f"Subject: {email.subject}")
                                    print(f"Date: {email.date}")
                                    print(f"Classification: {email.classification}")
                                    print(f"\nFlight segment:")
                                    print(f"  Route: {seg.get('departure_location')} -> {seg.get('arrival_location')}")
                                    print(f"  Departure: {dep_dt}")
                                    print(f"  Arrival: {arr_dt}")
                                    print(f"  Carrier: {seg.get('carrier_name')}")
                                    print(f"\nBooking type: {booking_data.get('booking_type')}")
                                    print(f"Status: {booking_data.get('status')}")
                                    print("-" * 80)
                                    
                    except Exception as e:
                        if str(e) != "'NoneType' object is not iterable":
                            print(f"Error processing {email.email_id}: {e}")
                            
        # Also check for any flight bookings in June
        print("\n=== All June flight bookings ===\n")
        
        for email, content in oslo_emails:
            if content.extracted_booking_info:
                try:
                    booking_data = json.loads(content.extracted_booking_info)
                    
                    if 'transport_segments' in booking_data:
                        for seg in booking_data['transport_segments']:
                            dep_dt = seg.get('departure_datetime')
                            if dep_dt and '2025-06' in str(dep_dt):
                                print(f"June flight:")
                                print(f"  Email: {email.email_id} - {email.subject[:60]}...")
                                print(f"  Route: {seg.get('departure_location')} -> {seg.get('arrival_location')}")
                                print(f"  Departure: {dep_dt}")
                                print(f"  Arrival: {seg.get('arrival_datetime')}")
                                if 'zurich' in str(seg.get('departure_location', '')).lower() or \
                                   'oslo' in str(seg.get('arrival_location', '')).lower() or \
                                   'gardermoen' in str(seg.get('arrival_location', '')).lower():
                                    print("  *** RELEVANT TO OSLO TRIP ***")
                                print("-" * 40)
                                
                except:
                    pass
                    
    finally:
        db.close()

if __name__ == "__main__":
    check_incomplete_bookings()