#!/usr/bin/env python3
"""
Add booking extraction fields to email_content table
"""
import os
import sys
import sqlite3
import logging

# Add backend directory to Python path
sys.path.append(os.path.dirname(__file__))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_path():
    """Get database path from config"""
    try:
        from lib.config_manager import config_manager
        return config_manager.get_database_path()
    except ImportError:
        # Fallback to default path
        parent_dir = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(parent_dir, "data", "mytrips.db")


def add_booking_extraction_fields():
    """Add booking extraction fields to email_content table"""
    db_path = get_database_path()
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("Adding booking extraction fields to email_content table...")
        
        # Check if fields already exist
        cursor.execute("PRAGMA table_info(email_content)")
        columns = [column[1] for column in cursor.fetchall()]
        
        fields_to_add = [
            ("booking_extraction_status", "VARCHAR(50) DEFAULT 'pending'"),
            ("extracted_booking_info", "TEXT"),
            ("booking_extraction_error", "TEXT")
        ]
        
        fields_added = 0
        for field_name, field_definition in fields_to_add:
            if field_name not in columns:
                logger.info(f"Adding field: {field_name}")
                cursor.execute(f"ALTER TABLE email_content ADD COLUMN {field_name} {field_definition}")
                fields_added += 1
            else:
                logger.info(f"Field {field_name} already exists, skipping")
        
        # Create index for booking_extraction_status
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_content_booking_status ON email_content(booking_extraction_status)")
            logger.info("Created index for booking_extraction_status")
        except Exception as e:
            logger.warning(f"Could not create index: {e}")
        
        conn.commit()
        conn.close()
        
        if fields_added > 0:
            logger.info(f"✅ Successfully added {fields_added} booking extraction fields")
        else:
            logger.info("✅ All booking extraction fields already exist")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to add fields: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Main function"""
    print("=" * 60)
    print("Booking Extraction Fields Migration")
    print("=" * 60)
    print()
    print("This will add the following fields to email_content table:")
    print("- booking_extraction_status (VARCHAR(50) DEFAULT 'pending')")
    print("- extracted_booking_info (TEXT)")
    print("- booking_extraction_error (TEXT)")
    print()
    
    # Ask for confirmation
    response = input("Continue with migration? (y/n): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return False
    
    print()
    success = add_booking_extraction_fields()
    
    if success:
        print("\n🎉 Database migration completed successfully!")
        print("The booking extraction fields have been added to email_content table.")
        print("You can now use the two-step trip detection feature:")
        print("1. Extract Bookings (Step 1)")
        print("2. Trip Detection (Step 2)")
    else:
        print("\n❌ Database migration failed")
        print("Please check the error messages above.")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)