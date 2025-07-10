"""
Core Trip Detection Logic - Pure business logic without database dependencies
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from lib.ai.ai_provider_interface import AIProviderInterface

logger = logging.getLogger(__name__)


class TripDetector:
    """Core trip detection logic using Gemini AI"""
    
    def __init__(self, ai_provider: AIProviderInterface):
        self.ai_provider = ai_provider
    
    def detect_trips(self, emails: List[Dict], existing_trips: List[Dict] = None) -> List[Dict]:
        """
        Analyze emails and detect trips using AI
        
        Args:
            emails: List of email data with extracted booking information
            existing_trips: List of existing trips to consider for merging
            
        Returns:
            List of all trips (existing + new/updated)
        """
        try:
            # All emails should already be booking emails (filtered at database level)
            if not emails:
                logger.info("No emails to process")
                return existing_trips or []
            
            logger.info(f"Processing {len(emails)} booking emails with {len(existing_trips or [])} existing trips")
            
            # Create AI prompt
            prompt = self._create_trip_detection_prompt(emails, existing_trips)
            
            # Log request details for diagnostics
            prompt_length = len(prompt)
            logger.info(f"Sending AI request - Length: {prompt_length:,} characters, Booking emails: {len(emails)}, Existing trips: {len(existing_trips or [])}")
            
            # Call AI provider and get full response with token usage
            ai_response = self.ai_provider.generate_content(prompt)
            
            # Extract response text and token information
            response_text = ai_response['content']
            input_tokens = ai_response['input_tokens']
            output_tokens = ai_response['output_tokens']
            total_tokens = ai_response['total_tokens']
            estimated_cost = ai_response['estimated_cost_usd']
            
            # Log response details for diagnostics
            response_length = len(response_text)
            logger.info(f"Received AI response - Length: {response_length:,} characters")
            logger.info(f"Token usage - Input: {input_tokens:,}, Output: {output_tokens:,}, Total: {total_tokens:,}")
            logger.info(f"Estimated cost: ${estimated_cost:.4f} USD")
            
            
            # Log full response for diagnosis (using DEBUG level to reduce log noise)
            logger.debug(f"Full AI response: {response_text}")
            
            # Parse response
            trips = self._parse_ai_response(response_text, emails)
            
            if trips:
                logger.info(f"Successfully detected {len(trips)} trips")
                return trips
            else:
                logger.warning("No trips detected from AI response")
                return existing_trips or []
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Trip detection failed: {error_msg}")
            
            # Log additional context for debugging
            logger.error(f"Context - Booking emails: {len(emails)}, Existing trips: {len(existing_trips or [])}")
            if hasattr(e, '__class__'):
                logger.error(f"Exception type: {e.__class__.__name__}")
            
            # Check if this is a critical AI API error that should stop processing
            if "500" in error_msg or "internal error" in error_msg.lower() or "quota" in error_msg.lower():
                logger.error("Critical AI API error detected - returning None to indicate failure")
                return None
            # Return existing trips for non-critical errors
            return existing_trips or []
    
    def _format_email_ids_safely(self, segments: List[Dict]) -> str:
        """Safely format email IDs from transport segments"""
        try:
            email_ids = []
            for seg in segments:
                related_ids = seg.get('related_email_ids', [])
                if related_ids and isinstance(related_ids, list):
                    # Take first email ID from each segment
                    if len(related_ids) > 0 and isinstance(related_ids[0], str):
                        email_ids.append(related_ids[0][:8])  # First 8 chars
            return ', '.join(email_ids) if email_ids else 'none'
        except Exception as e:
            logger.warning(f"Error formatting email IDs: {e}")
            return 'error'
    
    def _create_trip_detection_prompt(self, emails: List[Dict], existing_trips: List[Dict] = None) -> str:
        """Create comprehensive prompt for trip detection"""
        # Sort emails by date for better context
        sorted_emails = sorted(emails, key=lambda x: x.get('date', ''))
        
        # Build email list for prompt using extracted booking information
        email_list = []
        for i, email in enumerate(sorted_emails):
            booking_info = email.get('extracted_booking_info', {})
            booking_summary = json.dumps(booking_info, indent=2) if booking_info else "No booking information extracted"
            
            email_summary = f"""
Email {i+1}:
- ID: {email.get('email_id', 'unknown')}
- Date: {email.get('date', 'unknown')}
- Subject: {email.get('subject', 'unknown')}
- From: {email.get('sender', 'unknown')}
- Type: {email.get('classification', 'unknown')}
- Extracted Booking Information:
{booking_summary}
"""
            email_list.append(email_summary)
        
        emails_text = "\n".join(email_list)
        
        # Format existing trips if provided
        existing_trips_text = ""
        if existing_trips:
            existing_trips_summary = []
            for idx, trip in enumerate(existing_trips):
                trip_summary = f"""
Trip {idx + 1}: {trip.get('name', 'Unknown')}
- Dates: {trip.get('start_date', 'unknown')} to {trip.get('end_date', 'unknown')}
- Cities: {' → '.join(trip.get('cities_visited', []))}
- Total Cost: {trip.get('total_cost', 0)}
- Transport Segments: {len(trip.get('transport_segments', []))}
- Accommodations: {len(trip.get('accommodations', []))}
- Activities: {len(trip.get('tour_activities', []))}
- Related Email IDs: {self._format_email_ids_safely(trip.get('transport_segments', [])[:3])}...
"""
                existing_trips_summary.append(trip_summary)
            
            existing_trips_text = f"""
CRITICAL: The following trips ALREADY EXIST in the system (from database and previous processing). You MUST:
1. Include ALL existing trips in your response (they are the baseline)
2. Check if any NEW bookings in the current email batch belong to existing trips
3. If new bookings belong to existing trips, ADD them to those trips and update the trip details
4. If new bookings form separate trips, CREATE new trips
5. Return ALL trips (existing + updated + new) - DO NOT omit any existing trips

EXISTING TRIPS (MUST be included in response):
{"".join(existing_trips_summary)}

When updating existing trips with new bookings:
- Add new segments/accommodations/activities to the appropriate existing trip
- Update the trip's end date if new bookings extend the trip
- Update the total cost by adding new costs
- Add new cities to cities_visited if needed  
- Maintain chronological order in segments
- Update related_email_ids to include the new emails

IMPORTANT: Your response must contain ALL {len(existing_trips)} existing trips plus any new trips you detect.
"""
        
        prompt = f"""You are analyzing STRUCTURED BOOKING INFORMATION that has been pre-extracted from travel emails. Your task is to detect distinct trips and organize related bookings.

CRITICAL: You MUST respond with ONLY valid JSON. Do NOT include any explanatory text, comments, or markdown formatting. Output ONLY the JSON structure starting with {{ and ending with }}.

The traveler lives in Zurich, so trips typically start and end there.
{existing_trips_text}

For each trip, identify:
1. Trip boundaries (departure from and return to Zurich)
2. All cities visited in chronological order
3. Related bookings (flights, hotels, tours, cruises)
4. Relationships between bookings (original bookings, changes, cancellations)
5. Total cost calculation
6. Distance information for transport segments

IMPORTANT RULES FOR BOOKING RELATIONSHIPS:
- Use confirmation_numbers to link related bookings
- Use original_booking_reference to connect cancellations/changes to original bookings
- If a booking has status="cancelled", mark it as cancelled in the output
- If a booking has status="modified", check if there's a newer version with the same confirmation number
- Only keep the latest version of modified bookings as active (is_latest_version=true)
- Group bookings by travel dates to identify trip boundaries

DISTANCE HANDLING:
- If extracted booking info contains distance_km and distance_type, use those values directly
- If distance info is missing, estimate based on locations:
  - Common distances from Zurich: Paris ~490km, London ~780km, Munich ~240km, Vienna ~600km, Rome ~680km, Barcelona ~860km
  - Set distance_type="straight" for estimated distances
  - Set distance_type="actual" only when using provided distance data

TRIP BOUNDARY DETECTION:
- A trip starts with departure from Zurich and ends with return to Zurich
- Group bookings that are close in time (within reasonable travel periods)
- Multi-city trips should be kept as single trips
- Consider layovers and connections as part of the same trip

Output ONLY this JSON structure (no additional text):
{{
  "trips": [
    {{
      "name": "Trip to [main destinations]",
      "destination": "[primary destination city]",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD", 
      "cities_visited": ["Zurich", "City1", "City2", ..., "Zurich"],
      "total_cost": 0.00,
      "transport_segments": [
        {{
          "segment_type": "flight|train|bus|ferry",
          "departure_location": "City, Country",
          "arrival_location": "City, Country",
          "departure_datetime": "YYYY-MM-DD HH:MM",
          "arrival_datetime": "YYYY-MM-DD HH:MM",
          "carrier_name": "Airline/Railway",
          "segment_number": "Flight/Train number",
          "distance_km": 1234.5,
          "distance_type": "actual|straight",
          "cost": 0.00,
          "booking_platform": "Platform name",
          "confirmation_number": "ABC123",
          "status": "confirmed|cancelled|modified",
          "is_latest_version": true|false,
          "related_email_ids": ["email_id1", "email_id2"]
        }}
      ],
      "accommodations": [
        {{
          "property_name": "Hotel Name",
          "check_in_date": "YYYY-MM-DD",
          "check_out_date": "YYYY-MM-DD",
          "address": "Full address",
          "city": "City",
          "country": "Country",
          "cost": 0.00,
          "booking_platform": "Platform name",
          "confirmation_number": "ABC123",
          "status": "confirmed|cancelled|modified",
          "is_latest_version": true|false,
          "related_email_ids": ["email_id1", "email_id2"]
        }}
      ],
      "tour_activities": [
        {{
          "activity_name": "Tour/Activity name",
          "description": "Brief description",
          "start_datetime": "YYYY-MM-DD HH:MM",
          "end_datetime": "YYYY-MM-DD HH:MM",
          "location": "Location",
          "city": "City",
          "cost": 0.00,
          "booking_platform": "Platform name",
          "confirmation_number": "ABC123",
          "status": "confirmed|cancelled|modified",
          "is_latest_version": true|false,
          "related_email_ids": ["email_id1"]
        }}
      ],
      "cruises": [
        {{
          "cruise_line": "Cruise Line Name",
          "ship_name": "Ship Name",
          "departure_datetime": "YYYY-MM-DD HH:MM",
          "arrival_datetime": "YYYY-MM-DD HH:MM",
          "itinerary": ["Port1", "Port2", "Port3"],
          "cost": 0.00,
          "booking_platform": "Platform name",
          "confirmation_number": "ABC123", 
          "status": "confirmed|cancelled|modified",
          "is_latest_version": true|false,
          "related_email_ids": ["email_id1"]
        }}
      ]
    }}
  ]
}}

Emails to analyze:
{emails_text}

Remember:
- You are working with PRE-EXTRACTED structured booking information, not raw email content
- Use confirmation_numbers and original_booking_reference fields to link related bookings
- Respect the status field from extracted data (confirmed/cancelled/modified)
- Mark cancelled bookings appropriately in your output
- Only latest versions should have is_latest_version=true
- Every transport segment should have distance information:
  * Use distance_km and distance_type from extracted data if available
  * If missing, estimate based on departure/arrival locations
  * Examples: ZUR-CDG (Paris) 490km, ZUR-LHR (London) 780km, ZUR-MUC (Munich) 240km
  * ALWAYS include both distance_km (number) and distance_type ("actual" or "straight")
  * Use "actual" only when using provided distance data from extraction
  * Use "straight" for your estimates
  * Never leave distance fields empty or null

FINAL REMINDER: Output ONLY valid JSON starting with {{ and ending with }}. NO other text."""

        return prompt
    
    def _parse_ai_response(self, response_text: str, emails: List[Dict]) -> List[Dict]:
        """Parse AI response and create trip structures"""
        try:
            # Extract JSON from response
            response_text = response_text.strip()
            
            # First try to extract JSON from code blocks
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
            
            # Try to find JSON object directly in the text
            # Look for the start of the JSON object
            json_start = response_text.find('{')
            if json_start >= 0:
                # Extract from the first '{' to the last '}'
                json_end = response_text.rfind('}')
                if json_end > json_start:
                    response_text = response_text[json_start:json_end + 1]
            
            result = json.loads(response_text.strip())
            trips = result.get('trips', [])
            
            # Store safe metadata from AI analysis (avoid circular reference)
            analysis_metadata = {
                'total_trips_detected': len(trips),
                'response_timestamp': datetime.now().isoformat(),
                'has_transport_segments': any(trip.get('transport_segments') for trip in trips),
                'has_accommodations': any(trip.get('accommodations') for trip in trips),
                'has_activities': any(trip.get('tour_activities') for trip in trips)
            }
            
            for trip in trips:
                trip['gemini_analysis'] = analysis_metadata
            
            return trips
            
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            logger.error(f"Response was: {response_text[:500]}...")
            # Raise exception instead of returning empty list so the service knows there was an error
            raise Exception(f"Failed to parse AI response: {str(e)}")