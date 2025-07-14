#!/usr/bin/env python3
"""
Test script for new microservices architecture
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from backend.services.orchestrators.email_processing_orchestrator import EmailProcessingOrchestrator
from backend.database.config import SessionLocal
from backend.database.models import Email, EmailContent
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_microservices():
    """Test the new microservices architecture"""
    
    print("\n=== Testing Microservices Architecture ===\n")
    
    # Create orchestrator
    orchestrator = EmailProcessingOrchestrator()
    
    # Test 1: Import emails from last 7 days
    print("1. Testing email import (last 7 days)...")
    try:
        result = orchestrator.import_and_process_days(
            days=7,
            process_immediately=False  # Don't auto-classify
        )
        print(f"   ✓ Import successful: {result['new_count']} new emails, {result['skipped_count']} skipped")
    except Exception as e:
        print(f"   ✗ Import failed: {e}")
        return
    
    # Test 2: Classification
    print("\n2. Testing email classification...")
    try:
        # Get some unclassified emails
        db = SessionLocal()
        unclassified_ids = db.query(Email.email_id).filter(
            Email.classification == 'unclassified'
        ).limit(5).all()
        db.close()
        
        if unclassified_ids:
            email_ids = [id[0] for id in unclassified_ids]
            result = orchestrator.process_classification(
                email_ids=email_ids,
                auto_continue=False
            )
            print(f"   ✓ Classification successful: {len(result.get('classifications', []))} emails classified")
            print(f"   Travel emails found: {len(result.get('travel_email_ids', []))}")
        else:
            print("   ⚠ No unclassified emails found")
    except Exception as e:
        print(f"   ✗ Classification failed: {e}")
    
    # Test 3: Content extraction
    print("\n3. Testing content extraction...")
    try:
        # Get some travel emails without content
        db = SessionLocal()
        from backend.constants import TRAVEL_CATEGORIES
        
        travel_emails = db.query(Email.email_id).filter(
            Email.classification.in_(TRAVEL_CATEGORIES)
        ).outerjoin(EmailContent).filter(
            EmailContent.email_id.is_(None)
        ).limit(3).all()
        db.close()
        
        if travel_emails:
            email_ids = [id[0] for id in travel_emails]
            result = orchestrator.process_content_extraction(
                email_ids=email_ids,
                auto_continue=False
            )
            print(f"   ✓ Content extraction successful: {result.get('success_count', 0)} emails processed")
        else:
            print("   ⚠ No travel emails needing content extraction found")
    except Exception as e:
        print(f"   ✗ Content extraction failed: {e}")
    
    # Test 4: Booking extraction
    print("\n4. Testing booking extraction...")
    try:
        # Get emails with content but no booking extraction
        db = SessionLocal()
        emails_for_booking = db.query(Email.email_id).join(EmailContent).filter(
            Email.classification.in_(TRAVEL_CATEGORIES),
            EmailContent.extraction_status == 'completed',
            EmailContent.booking_extraction_status == 'pending'
        ).limit(3).all()
        db.close()
        
        if emails_for_booking:
            email_ids = [id[0] for id in emails_for_booking]
            result = orchestrator.process_booking_extraction(email_ids=email_ids)
            print(f"   ✓ Booking extraction successful: {result.get('success_count', 0)} emails processed")
            print(f"   Reclassified as non-travel: {result.get('reclassified_count', 0)}")
        else:
            print("   ⚠ No emails needing booking extraction found")
    except Exception as e:
        print(f"   ✗ Booking extraction failed: {e}")
    
    # Test 5: Full pipeline with date range
    print("\n5. Testing full pipeline (last 2 days)...")
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=2)
        
        result = orchestrator.process_full_pipeline(start_date, end_date)
        
        print(f"   ✓ Full pipeline completed:")
        print(f"     - Imported: {result['import'].get('new_count', 0)} new emails")
        print(f"     - Classified: {len(result['classification'].get('classifications', []))} emails")
        print(f"     - Content extracted: {result['content_extraction'].get('success_count', 0)} emails")
        print(f"     - Bookings extracted: {result['booking_extraction'].get('success_count', 0)} emails")
    except Exception as e:
        print(f"   ✗ Full pipeline failed: {e}")
    
    print("\n=== Testing Complete ===\n")

if __name__ == "__main__":
    test_microservices()