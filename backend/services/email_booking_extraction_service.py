"""
Email Booking Extraction Service - Step 1: Extract booking information from individual emails
"""
import threading
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from database.config import SessionLocal
from database.models import Email, EmailContent
from lib.ai.ai_provider_factory import AIProviderFactory
from lib.ai.ai_provider_interface import AIProviderInterface

logger = logging.getLogger(__name__)


class EmailBookingExtractionService:
    """Service for extracting booking information from individual travel emails"""
    
    def __init__(self):
        self.ai_provider: Optional[AIProviderInterface] = None
        try:
            # Create AI provider using factory - using openai-fast model for extraction
            self.ai_provider = AIProviderFactory.create_provider(
                model_tier='fast',
                provider_name='openai'
            )
            model_info = self.ai_provider.get_model_info()
            logger.info(f"AI provider initialized for booking extraction: {model_info['model_name']}")
        except Exception as e:
            logger.error(f"Failed to initialize AI provider: {e}")
        
        # Progress tracking with thread safety
        self.extraction_progress = {
            'is_running': False,
            'total_emails': 0,
            'processed_emails': 0,
            'extracted_count': 0,
            'failed_count': 0,
            'current_batch': 0,
            'total_batches': 0,
            'finished': False,
            'error': None,
            'message': ''
        }
        self._stop_flag = threading.Event()
        self._extraction_thread = None
        self._lock = threading.Lock()
    
    def start_extraction(self, date_range: Optional[Dict] = None) -> Dict:
        """Start booking information extraction process"""
        with self._lock:
            if self.extraction_progress.get('is_running', False):
                return {"started": False, "message": "Booking extraction already in progress"}
            
            if self._extraction_thread and self._extraction_thread.is_alive():
                return {"started": False, "message": "Extraction thread already running"}
            
            if not self.ai_provider:
                return {"started": False, "message": "AI provider not available"}
            
            # Reset progress
            self._stop_flag.clear()
            self.extraction_progress = {
                'is_running': True,
                'total_emails': 0,
                'processed_emails': 0,
                'extracted_count': 0,
                'failed_count': 0,
                'current_batch': 0,
                'total_batches': 0,
                'finished': False,
                'error': None,
                'message': 'Starting booking extraction...',
                'start_time': datetime.now()
            }
            
            # Start background thread
            self._extraction_thread = threading.Thread(
                target=self._background_extraction,
                args=(date_range,),
                daemon=True
            )
            self._extraction_thread.start()
            
            return {"started": True, "message": "Booking extraction started"}
    
    def stop_extraction(self) -> str:
        """Stop ongoing extraction process"""
        with self._lock:
            self._stop_flag.set()
            if self.extraction_progress.get('is_running', False):
                self.extraction_progress['is_running'] = False
                self.extraction_progress['finished'] = True
                self.extraction_progress['message'] = 'Extraction stopped by user'
        return "Stop signal sent"
    
    def get_extraction_progress(self) -> Dict:
        """Get current extraction progress"""
        progress = self.extraction_progress.copy()
        
        # Calculate progress percentage
        if progress['total_emails'] > 0:
            progress['progress'] = int((progress['processed_emails'] / progress['total_emails']) * 100)
        else:
            progress['progress'] = 0
            
        return progress
    
    def _background_extraction(self, date_range: Optional[Dict] = None):
        """Background process for booking extraction"""
        db = SessionLocal()
        try:
            # Fetch all travel-related emails with content but no booking extraction
            travel_categories = [
                'flight', 'hotel', 'car_rental', 'train', 'cruise', 
                'tour', 'travel_insurance', 'flight_change', 
                'hotel_change', 'other_travel'
            ]
            
            query = db.query(Email).join(EmailContent).filter(
                Email.classification.in_(travel_categories),
                EmailContent.extraction_status == 'completed',
                EmailContent.booking_extraction_status.in_(['pending', 'failed'])
            )
            
            if date_range:
                if 'start_date' in date_range:
                    query = query.filter(Email.timestamp >= date_range['start_date'])
                if 'end_date' in date_range:
                    query = query.filter(Email.timestamp <= date_range['end_date'])
            
            # Order by timestamp for chronological processing
            emails = query.order_by(Email.timestamp.asc()).all()
            
            if not emails:
                with self._lock:
                    self.extraction_progress.update({
                        'finished': True,
                        'is_running': False,
                        'message': 'No emails found that need booking extraction'
                    })
                return
            
            # Update progress
            self.extraction_progress['total_emails'] = len(emails)
            
            # Skip cost estimation for now since we're using AI provider interface
            # TODO: Add cost estimation to AI provider interface
            
            self.extraction_progress['message'] = f'Found {len(emails)} emails to extract booking information'
            
            # Process emails in smaller batches for booking extraction (10 emails per batch)
            batch_size = 10
            total_batches = (len(emails) + batch_size - 1) // batch_size
            self.extraction_progress['total_batches'] = total_batches
            
            extracted_count = 0
            failed_count = 0
            
            for batch_num in range(total_batches):
                if self._stop_flag.is_set():
                    break
                
                start_idx = batch_num * batch_size
                end_idx = min((batch_num + 1) * batch_size, len(emails))
                batch_emails = emails[start_idx:end_idx]
                
                self.extraction_progress['current_batch'] = batch_num + 1
                self.extraction_progress['message'] = f'Processing batch {batch_num + 1}/{total_batches}'
                
                # Process each email individually in this batch
                for email in batch_emails:
                    if self._stop_flag.is_set():
                        break
                    
                    try:
                        success = self._extract_single_email_booking(email, db)
                        if success:
                            extracted_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to extract booking info from email {email.email_id}: {e}")
                        failed_count += 1
                    
                    self.extraction_progress['processed_emails'] += 1
                    self.extraction_progress['extracted_count'] = extracted_count
                    self.extraction_progress['failed_count'] = failed_count
            
            # Mark as finished
            with self._lock:
                self.extraction_progress.update({
                    'finished': True,
                    'is_running': False,
                    'message': f'Extraction completed. {extracted_count} extracted, {failed_count} failed.'
                })
            
        except Exception as e:
            logger.error(f"Booking extraction failed: {e}")
            with self._lock:
                self.extraction_progress.update({
                    'finished': True,
                    'is_running': False,
                    'error': str(e),
                    'message': f'Extraction failed: {str(e)}'
                })
        finally:
            db.close()
    
    def _extract_single_email_booking(self, email: Email, db: Session) -> bool:
        """Extract booking information from a single email"""
        try:
            content = email.email_content
            if not content:
                logger.warning(f"No content found for email {email.email_id}")
                return False
            
            # Update status to extracting
            content.booking_extraction_status = 'extracting'
            db.commit()
            
            # Create AI prompt for booking extraction
            prompt = self._create_booking_extraction_prompt(email, content)
            
            # Call AI provider - use simple method that returns just the content string
            response_text = self.ai_provider.generate_content_simple(prompt)
            
            # Parse response
            booking_info = self._parse_booking_response(response_text)
            
            if booking_info:
                # Check if this is a non-booking email
                if booking_info.get('booking_type') is None:
                    # This is a non-booking email (reminder, marketing, etc.)
                    content.extracted_booking_info = json.dumps(booking_info, ensure_ascii=False)
                    content.booking_extraction_status = 'no_booking'
                    content.booking_extraction_error = booking_info.get('reason', 'Non-booking email')
                    db.commit()
                    
                    logger.info(f"Email {email.email_id} identified as non-booking: {booking_info.get('non_booking_type', 'unknown')}")
                    return True
                else:
                    # This is a booking email with extracted information
                    content.extracted_booking_info = json.dumps(booking_info, ensure_ascii=False)
                    content.booking_extraction_status = 'completed'
                    content.booking_extraction_error = None
                    db.commit()
                    
                    logger.info(f"Successfully extracted booking info from email {email.email_id}")
                    return True
            else:
                # Mark as failed
                content.booking_extraction_status = 'failed'
                content.booking_extraction_error = 'Failed to parse booking information'
                db.commit()
                return False
                
        except Exception as e:
            logger.error(f"Error extracting booking info from email {email.email_id}: {e}")
            # Mark as failed
            content.booking_extraction_status = 'failed'
            content.booking_extraction_error = str(e)
            db.commit()
            return False
    
    def _create_booking_extraction_prompt(self, email: Email, content: EmailContent) -> str:
        """Create prompt for extracting booking information from a single email"""
        
        # Get full content
        full_content = content.content_text or content.content_html or ''
        
        # Get attachment info
        attachments = []
        if content.attachments_info:
            try:
                attachments = json.loads(content.attachments_info)
            except:
                pass
        
        prompt = f"""You are tasked with analyzing a travel-related email to determine if it contains actual booking information. This extracted information will later be used for:
1. Trip boundary detection (identifying which bookings belong to the same trip)
2. Booking relationship analysis (original bookings vs. changes/cancellations)
3. Duplicate detection and merging
4. Cost calculation and distance analysis

CRITICAL: First determine if this email contains actual booking information or if it's a NON-BOOKING email such as:
- Check-in reminders or notifications
- Travel tips or general information
- Marketing emails from travel companies
- Flight status updates without booking details
- Seat selection reminders
- Baggage information
- General travel advisories
- Survey requests
- Program enrollment confirmations (frequent flyer, hotel loyalty, etc.)

For NON-BOOKING emails, return: {{"booking_type": null, "non_booking_type": "reminder|marketing|status_update|check_in|general_info|survey|program_enrollment", "reason": "Brief explanation why this is not a booking"}}

For ACTUAL BOOKING emails, extract ALL relevant booking details, especially:
- Confirmation numbers/booking references (crucial for linking related emails)
- Dates and times (for trip boundary detection)
- Locations (departure/arrival cities, hotel addresses)
- Booking status (confirmed/cancelled/modified)
- Costs and currencies
- Any distance information mentioned
- Links to original bookings (for cancellation/change emails)

Email Details:
- Email ID: {email.email_id}
- Subject: {email.subject}
- From: {email.sender}
- Date: {email.timestamp.isoformat() if email.timestamp else email.date}
- Classification: {email.classification}
- Has Attachments: {len(attachments)} files

Full Email Content:
{full_content}

Attachment Information:
{json.dumps(attachments, indent=2) if attachments else "No attachments"}

Analyze the email and return a JSON object with this structure:

For NON-BOOKING emails:
{{
  "booking_type": null,
  "non_booking_type": "reminder|marketing|status_update|check_in|general_info|survey|program_enrollment",
  "reason": "Brief explanation why this is not a booking email"
}}

For ACTUAL BOOKING emails:
{{
  "booking_type": "flight|hotel|car_rental|train|cruise|tour|travel_insurance|cancellation|modification",
  "status": "confirmed|cancelled|modified|pending",
  "confirmation_numbers": ["ABC123", "DEF456"],
  "original_booking_reference": "XYZ789",  // For cancellations/changes, reference to original booking
  
  // Transport segments (ALWAYS an array, even for single segment)
  "transport_segments": [
    {{
      "segment_type": "flight|train|bus|ferry",
      "carrier_name": "Airline/Railway name",
      "segment_number": "LX123",
      "departure_location": "City, Country",
      "departure_airport_code": "ZUR",
      "arrival_location": "City, Country", 
      "arrival_airport_code": "CDG",
      "departure_datetime": "2024-01-15T14:30:00",
      "arrival_datetime": "2024-01-15T16:45:00",
      "distance_km": 490.5,
      "distance_type": "actual|straight",
      "booking_platform": "Platform name",
      "confirmation_number": "ABC123",
      "cost": 123.45
    }}
  ],
  
  // Accommodations (ALWAYS an array, even for single hotel)
  "accommodations": [
    {{
      "property_name": "Hotel Name",
      "address": "Full address",
      "city": "City",
      "country": "Country",
      "check_in_date": "2024-01-15",
      "check_out_date": "2024-01-17",
      "booking_platform": "Platform name",
      "confirmation_number": "HTL456",
      "cost": 234.56
    }}
  ],
  
  // Activities (ALWAYS an array, even for single activity)
  "activities": [
    {{
      "activity_name": "Tour name",
      "description": "Brief description",
      "start_datetime": "2024-01-16T09:00:00",
      "end_datetime": "2024-01-16T17:00:00",
      "location": "Location",
      "city": "City",
      "booking_platform": "Platform name",
      "confirmation_number": "TUR789",
      "cost": 89.00
    }}
  ],
  
  // Cruises (ALWAYS an array, even for single cruise)
  "cruises": [
    {{
      "cruise_line": "Cruise company",
      "ship_name": "Ship name",
      "departure_datetime": "2024-01-20T18:00:00",
      "arrival_datetime": "2024-01-27T08:00:00",
      "departure_port": "Port name",
      "arrival_port": "Port name",
      "itinerary": ["Port1", "Port2", "Port3"],
      "confirmation_number": "CRU012",
      "booking_platform": "Platform name",
      "cost": 1500.00
    }}
  ],
  
  "cost_info": {{
    "total_cost": 1234.56,
    "currency": "CHF|EUR|USD",
    "cost_breakdown": {{"base": 1000, "taxes": 234.56}}
  }},
  
  "dates": {{
    "booking_date": "2024-01-01",
    "travel_start_date": "2024-01-15",
    "travel_end_date": "2024-01-17"
  }},
  
  "additional_info": {{
    "passenger_names": ["John Doe"],
    "special_requests": "Vegetarian meal",
    "notes": "Any other relevant information"
  }}
}}

CRITICAL REQUIREMENTS:
1. FIRST AND MOST IMPORTANT: Determine if this is a booking email or non-booking email
   - NON-BOOKING: Check-in reminders, status updates, marketing, surveys, etc. → Return booking_type: null
   - BOOKING: Actual reservations, confirmations, cancellations, modifications → Extract full details

2. For NON-BOOKING emails:
   - Set "booking_type": null
   - Specify "non_booking_type" (reminder|marketing|status_update|check_in|general_info|survey|program_enrollment)
   - Provide brief "reason" explaining why it's not a booking

3. For BOOKING emails only:
   - ARRAY FORMAT IS MANDATORY: ALL booking details MUST be in arrays (transport_segments, accommodations, activities, cruises)
   - Even for single items, use an array with one element: transport_segments: [{{...}}] NOT transport_details: {{...}}
   - CONFIRMATION NUMBERS are EXTREMELY IMPORTANT - Extract ALL confirmation numbers/booking references mentioned in the email
   - For cancellation/change emails, ALWAYS include the original booking reference in "original_booking_reference"
   - Include confirmation numbers in BOTH the main "confirmation_numbers" array AND in each segment/accommodation/activity
   - Field names must match exactly: "carrier_name" (not "carrier"), "segment_number" (not "flight_number")
   - If distances are mentioned (flight miles, etc.), include them and mark distance_type as "actual"
   - Include exact dates and times when available
   - Use English values only (no Chinese characters in the JSON)
   - If information is not available, use null instead of guessing
   - For multi-segment trips, include ALL segments in the transport_segments array
   - Look for confirmation numbers in various formats: booking reference, confirmation code, PNR, reservation number, ticket number, etc.

Return only the JSON object, no additional text."""

        return prompt
    
    def _parse_booking_response(self, response_text: str) -> Optional[Dict]:
        """Parse Gemini response and extract booking information"""
        try:
            # Extract JSON from response
            response_text = response_text.strip()
            if '```json' in response_text:
                start = response_text.find('```json') + 7
                end = response_text.rfind('```')
                if end > start:
                    response_text = response_text[start:end]
            elif '```' in response_text:
                start = response_text.find('```') + 3
                end = response_text.rfind('```')
                if end > start:
                    response_text = response_text[start:end]
            
            booking_info = json.loads(response_text.strip())
            return booking_info
            
        except Exception as e:
            logger.error(f"Error parsing booking response: {e}")
            if 'response_text' in locals():
                logger.error(f"Response was: {response_text[:500]}...")
            return None