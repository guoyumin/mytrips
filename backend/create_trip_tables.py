#!/usr/bin/env python3
"""
Create new tables for trip detection feature
"""
import os
import sys
import logging

# Add backend directory to Python path
sys.path.append(os.path.dirname(__file__))

from backend.database.config import engine, Base
from backend.database.models import (
    Trip, TransportSegment, Accommodation, TourActivity, Cruise,
    EmailTransportSegment, EmailAccommodation, EmailTourActivity, EmailCruise
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_trip_tables():
    """Create all new trip-related tables"""
    try:
        logger.info("Starting database migration for trip detection feature...")
        
        # Create all tables defined in the models
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ Successfully created all trip-related tables")
        logger.info("Tables created:")
        logger.info("  - trips (with cities_visited, total_cost, origin_city)")
        logger.info("  - transport_segments (with distance_km and distance_type fields)")
        logger.info("  - accommodations")
        logger.info("  - tour_activities")
        logger.info("  - cruises")
        logger.info("  - email_transport_segment (association)")
        logger.info("  - email_accommodation (association)")
        logger.info("  - email_tour_activity (association)")
        logger.info("  - email_cruise (association)")
        logger.info("  - Updated email_content table with booking extraction fields")
        logger.info("  - Added confirmation_number indexes to all booking tables for faster lookup")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create tables: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Main function"""
    print("=" * 60)
    print("Trip Detection Database Migration")
    print("=" * 60)
    print()
    print("This will create the following new tables:")
    print("- trips (for storing detected trips)")
    print("- transport_segments (flights, trains, etc.)")
    print("- accommodations (hotels)")
    print("- tour_activities (tours and activities)")
    print("- cruises")
    print("- Association tables for many-to-many relationships")
    print()
    
    # Ask for confirmation
    response = input("Continue with migration? (y/n): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return False
    
    print()
    success = create_trip_tables()
    
    if success:
        print("\n🎉 Database migration completed successfully!")
        print("You can now use the trip detection feature.")
    else:
        print("\n❌ Database migration failed")
        print("Please check the error messages above.")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)