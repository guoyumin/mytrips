#!/usr/bin/env python3
"""
Find flights from Zurich with null datetime
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Email, EmailContent
import json

def find_zurich_flights():
    """Find flights from Zurich"""
    db = SessionLocal()
    try:
        # Get all emails with completed booking extraction
        completed_bookings = db.query(Email, EmailContent).join(
            EmailContent, Email.email_id == EmailContent.email_id
        ).filter(
            EmailContent.booking_extraction_status == 'completed'
        ).all()
        
        print(f"=== Searching {len(completed_bookings)} emails for Zurich flights ===\n")
        
        zurich_flights = []
        
        for email, content in completed_bookings:
            if content.extracted_booking_info:
                try:
                    booking_data = json.loads(content.extracted_booking_info)
                    
                    # Check transport_segments
                    if 'transport_segments' in booking_data:
                        for seg in booking_data['transport_segments']:
                            departure = seg.get('departure_location', '')
                            arrival = seg.get('arrival_location', '')
                            
                            # Check if flight is from Zurich
                            if departure and 'zurich' in departure.lower():
                                # Check if it has null datetime
                                if seg.get('departure_datetime') is None or seg.get('arrival_datetime') is None:
                                    print(f"FOUND: Flight with null datetime!")
                                    print(f"Email ID: {email.email_id}")
                                    print(f"Subject: {email.subject}")
                                    print(f"From: {email.sender}")
                                    print(f"Date: {email.date}")
                                    print(f"Classification: {email.classification}")
                                    print(f"\nFlight details:")
                                    print(f"  Route: {departure} -> {arrival}")
                                    print(f"  Departure: {seg.get('departure_datetime')}")
                                    print(f"  Arrival: {seg.get('arrival_datetime')}")
                                    print(f"  Carrier: {seg.get('carrier_name')}")
                                    print(f"  Flight: {seg.get('segment_number')}")
                                    print("\nFull segment data:")
                                    print(json.dumps(seg, indent=2))
                                    print("-" * 80)
                                    
                                # Also show flights to Oslo/Gardermoen
                                elif arrival and ('oslo' in arrival.lower() or 'gardermoen' in arrival.lower()):
                                    print(f"Zurich to Oslo/Gardermoen flight:")
                                    print(f"  Email: {email.email_id} - {email.subject[:60]}...")
                                    print(f"  Route: {departure} -> {arrival}")
                                    print(f"  Departure: {seg.get('departure_datetime')}")
                                    print(f"  Arrival: {seg.get('arrival_datetime')}")
                                    print("-" * 40)
                                    
                except Exception as e:
                    if str(e) != "'NoneType' object is not iterable":
                        print(f"Error processing {email.email_id}: {e}")
                        
    finally:
        db.close()

if __name__ == "__main__":
    find_zurich_flights()