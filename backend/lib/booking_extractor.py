"""
Booking Extraction Logic - Pure business logic without database dependencies
"""
import json
import logging
from typing import Dict, Optional
from backend.lib.ai.ai_provider_interface import AIProviderInterface

logger = logging.getLogger(__name__)


class BookingExtractor:
    """Core booking extraction logic using AI providers"""
    
    def __init__(self, ai_provider: AIProviderInterface):
        """
        Initialize booking extractor
        
        Args:
            ai_provider: AI provider instance for extraction
        """
        self.ai_provider = ai_provider
    
    def extract_booking(self, email_data: Dict) -> Dict:
        """
        Extract booking information from a single email
        
        Args:
            email_data: {
                'email_id': str,
                'subject': str,
                'sender': str,
                'classification': str,
                'content_text': str,
                'content_html': str,
                'attachments': List[Dict]
            }
            
        Returns:
            {
                'is_travel': bool,
                'booking_info': Dict or None,
                'actual_category': str (if misclassified),
                'reason': str (if not travel or no booking),
                'error': str or None
            }
        """
        try:
            # Create prompt
            prompt = self.create_booking_prompt(email_data)
            
            # Log AI model being used
            model_info = self.ai_provider.get_model_info()
            logger.info(f"Calling AI model for booking extraction: {model_info.get('provider', 'Unknown')} - {model_info['model_name']}")
            
            # Call AI provider
            response_text = self.ai_provider.generate_content_simple(prompt)
            
            # Parse response
            booking_info = self.parse_booking_response(response_text)
            
            if booking_info:
                return {
                    'is_travel': booking_info.get('is_travel', True),
                    'booking_info': booking_info,
                    'actual_category': booking_info.get('actual_category'),
                    'reason': booking_info.get('reason'),
                    'error': None
                }
            else:
                raise Exception("Failed to parse booking information from AI response")
                
        except Exception as e:
            logger.error(f"Failed to extract booking from email {email_data.get('email_id')}: {e}")
            return {
                'is_travel': True,  # Assume travel if error
                'booking_info': None,
                'error': str(e)
            }
    
    def create_booking_prompt(self, email_data: Dict) -> str:
        """Create prompt for extracting booking information from a single email"""
        
        # Get full content
        full_content = email_data.get('content_text') or email_data.get('content_html') or ''
        
        # Get attachment info
        attachments = email_data.get('attachments', [])
        
        prompt = f"""You are tasked with analyzing an email. Follow these steps:

STEP 1: VERIFY TRAVEL CLASSIFICATION
First, determine if this email is actually travel-related. Look for:
- Travel bookings (flights, hotels, car rentals, trains, cruises, tours)
- Travel confirmations, tickets, or itineraries
- Travel changes or cancellations
- Travel insurance policies

If the email is NOT travel-related (e.g., general marketing, non-travel purchases, personal emails, work emails, newsletters, etc.), return:
{{"is_travel": false, "actual_category": "not_travel", "reason": "Brief explanation why this is not travel-related"}}

STEP 2: FOR TRAVEL EMAILS - DETERMINE BOOKING STATUS
If the email IS travel-related, then determine if it contains actual booking information.

For NON-BOOKING travel emails (reminders, tips, status updates without booking details), return:
{{"is_travel": true, "booking_type": null, "non_booking_type": "reminder|marketing|status_update|check_in|general_info|survey|program_enrollment", "reason": "Brief explanation why this is not a booking"}}

For ACTUAL BOOKING emails, extract ALL relevant booking details:
- Confirmation numbers/booking references (crucial for linking related emails)
- Dates and times (for trip boundary detection)
- Locations (departure/arrival cities, hotel addresses)
- Booking status (confirmed/cancelled/modified)
- Costs and currencies
- Any distance information mentioned
- Links to original bookings (for cancellation/change emails)

Email Details:
- Email ID: {email_data.get('email_id', 'Unknown')}
- Subject: {email_data.get('subject', 'No subject')}
- From: {email_data.get('sender', 'Unknown sender')}
- Date: {email_data.get('date', 'Unknown date')}
- Classification: {email_data.get('classification', 'Unknown')}
- Has Attachments: {len(attachments)} files

Full Email Content:
{full_content}

Attachment Information:
{json.dumps(attachments, indent=2) if attachments else "No attachments"}

Analyze the email and return a JSON object with this structure:

For NON-TRAVEL emails:
{{
  "is_travel": false,
  "actual_category": "not_travel",
  "reason": "Brief explanation why this is not travel-related"
}}

For NON-BOOKING travel emails:
{{
  "is_travel": true,
  "booking_type": null,
  "non_booking_type": "reminder|marketing|status_update|check_in|general_info|survey|program_enrollment",
  "reason": "Brief explanation why this is not a booking email"
}}

For ACTUAL BOOKING emails:
{{
  "is_travel": true,
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
1. FIRST: Verify if this email is actually travel-related
   - If NOT travel-related → Return "is_travel": false with actual_category and reason
   - If travel-related → Continue to step 2

2. FOR TRAVEL EMAILS: Determine if this is a booking email or non-booking email
   - NON-BOOKING: Check-in reminders, status updates, marketing, surveys, etc. → Return booking_type: null
   - BOOKING: Actual reservations, confirmations, cancellations, modifications → Extract full details

3. For NON-TRAVEL emails:
   - Set "is_travel": false
   - Set "actual_category": "not_travel"
   - Provide brief "reason" explaining why it's not travel-related

4. For NON-BOOKING travel emails:
   - Set "is_travel": true
   - Set "booking_type": null
   - Specify "non_booking_type" (reminder|marketing|status_update|check_in|general_info|survey|program_enrollment)
   - Provide brief "reason" explaining why it's not a booking

5. For BOOKING emails only:
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

IMPORTANT: Return ONLY the JSON object. Do NOT include any thinking process, explanations, or additional text before or after the JSON. Do NOT use <think> tags or any other markup. Start your response directly with {{ and end with }}."""

        return prompt
    
    def parse_booking_response(self, response_text: str) -> Optional[Dict]:
        """Parse AI response and extract booking information"""
        try:
            # Extract JSON from response
            response_text = response_text.strip()
            
            # Remove <think> tags if present (for models like DeepSeek)
            if '<think>' in response_text and '</think>' in response_text:
                think_start = response_text.find('<think>')
                think_end = response_text.find('</think>') + len('</think>')
                if think_end > think_start:
                    response_text = response_text[:think_start] + response_text[think_end:]
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