#!/usr/bin/env python3
"""
Check if Oslo trip exists in database
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from database.config import SessionLocal
from database.models import Trip, TransportSegment, Accommodation
from sqlalchemy import or_
import json

def check_oslo_trips_in_db():
    """Check if Oslo trip exists in database"""
    db = SessionLocal()
    try:
        # Search for Oslo trips
        oslo_trips = db.query(Trip).filter(
            or_(
                Trip.name.ilike('%oslo%'),
                Trip.destination.ilike('%oslo%'),
                Trip.cities_visited.ilike('%oslo%')
            )
        ).all()
        
        print(f"=== Found {len(oslo_trips)} Oslo-related trips in database ===\n")
        
        for trip in oslo_trips:
            print(f"Trip ID: {trip.id}")
            print(f"Name: {trip.name}")
            print(f"Destination: {trip.destination}")
            print(f"Start Date: {trip.start_date}")
            print(f"End Date: {trip.end_date}")
            print(f"Cities Visited: {trip.cities_visited}")
            print(f"Total Cost: {trip.total_cost}")
            print(f"Created At: {trip.created_at}")
            
            # Check transport segments
            transports = db.query(TransportSegment).filter_by(trip_id=trip.id).all()
            print(f"\nTransport Segments ({len(transports)}):")
            for t in transports:
                print(f"  - {t.segment_type}: {t.departure_location} -> {t.arrival_location}")
                print(f"    Departure: {t.departure_datetime}")
                print(f"    Arrival: {t.arrival_datetime}")
                print(f"    Status: {t.status}")
                
            # Check accommodations
            accommodations = db.query(Accommodation).filter_by(trip_id=trip.id).all()
            print(f"\nAccommodations ({len(accommodations)}):")
            for a in accommodations:
                print(f"  - {a.property_name} in {a.city}")
                print(f"    Check-in: {a.check_in_date}")
                print(f"    Check-out: {a.check_out_date}")
                print(f"    Status: {a.status}")
                
            print("-" * 80)
            
    finally:
        db.close()

if __name__ == "__main__":
    check_oslo_trips_in_db()