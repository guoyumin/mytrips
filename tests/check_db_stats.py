#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.config import SessionLocal
from backend.database.models import Email, EmailContent, Trip
from backend.constants import TRAVEL_CATEGORIES

db = SessionLocal()
try:
    # Get statistics
    total_emails = db.query(Email).count()
    classified_emails = db.query(Email).filter(Email.classification != 'unclassified').count()
    travel_emails = db.query(Email).filter(Email.classification.in_(TRAVEL_CATEGORIES)).count()
    content_extracted = db.query(EmailContent).filter(EmailContent.extraction_status == 'completed').count()
    booking_extracted = db.query(EmailContent).filter(EmailContent.booking_extraction_status == 'completed').count()
    not_travel_reclassified = db.query(EmailContent).filter(EmailContent.booking_extraction_status == 'not_travel').count()
    
    print('=== Database Statistics ===')
    print(f'Total emails: {total_emails}')
    print(f'Classified emails: {classified_emails}')
    print(f'Travel emails: {travel_emails}')
    print(f'Content extracted: {content_extracted}')
    print(f'Bookings extracted: {booking_extracted}')
    print(f'Reclassified as not travel: {not_travel_reclassified}')
    
    # Show some sample emails
    print('\n=== Sample Travel Emails ===')
    travel_samples = db.query(Email).filter(Email.classification.in_(TRAVEL_CATEGORIES)).limit(3).all()
    for email in travel_samples:
        print(f'- {email.subject[:60]}... ({email.classification})')
        
except Exception as e:
    print(f'Error: {e}')
finally:
    db.close()