"""
BookingInfo domain model with business logic
"""
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class BookingType(str, Enum):
    FLIGHT = "flight"
    HOTEL = "hotel"
    CAR_RENTAL = "car_rental"
    TRAIN = "train"
    CRUISE = "cruise"
    TOUR = "tour"
    TRAVEL_INSURANCE = "travel_insurance"
    CANCELLATION = "cancellation"
    MODIFICATION = "modification"


class BookingStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    MODIFIED = "modified"
    PENDING = "pending"
    UNKNOWN = "unknown"


class NonBookingType(str, Enum):
    REMINDER = "reminder"
    MARKETING = "marketing"
    STATUS_UPDATE = "status_update"
    CHECK_IN = "check_in"
    GENERAL_INFO = "general_info"
    SURVEY = "survey"
    PROGRAM_ENROLLMENT = "program_enrollment"


class CostInfo(BaseModel):
    """Cost information for a booking"""
    total_cost: float = 0.0
    currency: Optional[str] = None
    cost_breakdown: Dict[str, float] = Field(default_factory=dict)


class BookingDates(BaseModel):
    """Date information for a booking"""
    booking_date: Optional[datetime] = None
    travel_start_date: Optional[datetime] = None
    travel_end_date: Optional[datetime] = None


class AdditionalInfo(BaseModel):
    """Additional booking information"""
    special_requests: Optional[str] = None
    notes: Optional[str] = None


class BookingInfo(BaseModel):
    """Domain model for booking information extracted from emails"""
    
    # Core fields
    booking_type: Optional[BookingType] = None
    non_booking_type: Optional[NonBookingType] = None
    reason: Optional[str] = None  # For non-booking emails
    status: BookingStatus = BookingStatus.UNKNOWN
    confirmation_numbers: List[str] = Field(default_factory=list)
    original_booking_reference: Optional[str] = None  # For cancellations/changes
    
    # Booking segments (using lists to match the extraction format)
    transport_segments: List[Dict[str, Any]] = Field(default_factory=list)
    accommodations: List[Dict[str, Any]] = Field(default_factory=list)
    activities: List[Dict[str, Any]] = Field(default_factory=list)
    cruises: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Cost and date information
    cost_info: Optional[CostInfo] = None
    dates: Optional[BookingDates] = None
    additional_info: Optional[AdditionalInfo] = None
    
    # Metadata
    email_id: Optional[str] = None
    extracted_at: Optional[datetime] = None
    
    @validator('confirmation_numbers', pre=True)
    def ensure_list(cls, v):
        """Ensure confirmation numbers is always a list"""
        if isinstance(v, str):
            return [v]
        return v or []
    
    def is_booking(self) -> bool:
        """Check if this is an actual booking (not a non-booking email)"""
        return self.booking_type is not None
    
    def is_complete(self) -> bool:
        """
        Check if the booking information is complete enough for trip detection.
        Migrated from _is_email_complete in trip_detection_service.py
        """
        if not self.is_booking():
            return False
        
        # Must have at least one booking segment
        has_segments = bool(
            self.transport_segments or 
            self.accommodations or 
            self.activities or 
            self.cruises
        )
        if not has_segments:
            return False
        
        # Check transport segments have required fields
        for segment in self.transport_segments:
            if not all([
                segment.get('departure_location'),
                segment.get('arrival_location'),
                segment.get('departure_datetime'),
                segment.get('arrival_datetime')
            ]):
                return False
        
        # Check accommodations have required fields
        for acc in self.accommodations:
            if not all([
                acc.get('property_name'),
                acc.get('check_in_date'),
                acc.get('check_out_date')
            ]):
                return False
        
        # Check activities have required fields
        for activity in self.activities:
            if not all([
                activity.get('activity_name'),
                activity.get('start_datetime')
            ]):
                return False
        
        # Check cruises have required fields
        for cruise in self.cruises:
            if not all([
                cruise.get('cruise_line'),
                cruise.get('departure_datetime'),
                cruise.get('arrival_datetime')
            ]):
                return False
        
        return True
    
    def is_zurich_local_trip(self) -> bool:
        """
        Check if this is a local trip within Zurich area.
        Migrated from _is_zurich_local_trip in trip_detection_service.py
        """
        if not self.is_booking():
            return False
        
        # Define Zurich area locations
        zurich_area = {
            'zurich', 'zürich', 'zuerich', 'winterthur', 'uster', 
            'dübendorf', 'dietikon', 'wetzikon', 'kloten', 'opfikon',
            'wallisellen', 'bülach', 'regensdorf', 'schlieren',
            'zurich airport', 'zürich flughafen', 'zrh'
        }
        
        # Check transport segments
        for segment in self.transport_segments:
            dep_loc = (segment.get('departure_location') or '').lower()
            arr_loc = (segment.get('arrival_location') or '').lower()
            
            # Check if both locations are in Zurich area
            dep_in_zurich = any(area in dep_loc for area in zurich_area)
            arr_in_zurich = any(area in arr_loc for area in zurich_area)
            
            if dep_in_zurich and arr_in_zurich:
                return True
        
        # Check if all activities are in Zurich
        if self.activities:
            all_in_zurich = all(
                any(area in (activity.get('city', '').lower() or 
                           activity.get('location', '').lower()) 
                    for area in zurich_area)
                for activity in self.activities
            )
            if all_in_zurich:
                return True
        
        return False
    
    def validate_for_trip_detection(self) -> tuple[bool, Optional[str]]:
        """
        Validate if this booking is suitable for trip detection.
        Returns (is_valid, reason)
        """
        if not self.is_booking():
            return False, f"Non-booking email: {self.non_booking_type}"
        
        if not self.is_complete():
            return False, "Incomplete booking information"
        
        if self.is_zurich_local_trip():
            return False, "Local Zurich trip"
        
        # Check for test bookings
        if self._is_test_booking():
            return False, "Test booking detected"
        
        return True, None
    
    def _is_test_booking(self) -> bool:
        """Check if this appears to be a test booking"""
        test_indicators = ['test', 'demo', 'sample', 'example']
        
        # Check confirmation numbers
        for conf_num in self.confirmation_numbers:
            if any(indicator in conf_num.lower() for indicator in test_indicators):
                return True
        
        # Additional info checks can be added here if needed
        
        return False
    
    def get_all_confirmation_numbers(self) -> List[str]:
        """Get all confirmation numbers from all segments"""
        all_numbers = set(self.confirmation_numbers)
        
        # Add from transport segments
        for segment in self.transport_segments:
            if segment.get('confirmation_number'):
                all_numbers.add(segment['confirmation_number'])
        
        # Add from accommodations
        for acc in self.accommodations:
            if acc.get('confirmation_number'):
                all_numbers.add(acc['confirmation_number'])
        
        # Add from activities
        for activity in self.activities:
            if activity.get('confirmation_number'):
                all_numbers.add(activity['confirmation_number'])
        
        # Add from cruises
        for cruise in self.cruises:
            if cruise.get('confirmation_number'):
                all_numbers.add(cruise['confirmation_number'])
        
        return list(all_numbers)
    
    def get_travel_date_range(self) -> tuple[Optional[datetime], Optional[datetime]]:
        """Get the overall travel date range from all segments"""
        dates = []
        
        # Collect from transport segments
        for segment in self.transport_segments:
            if segment.get('departure_datetime'):
                dates.append(datetime.fromisoformat(segment['departure_datetime']))
            if segment.get('arrival_datetime'):
                dates.append(datetime.fromisoformat(segment['arrival_datetime']))
        
        # Collect from accommodations
        for acc in self.accommodations:
            if acc.get('check_in_date'):
                dates.append(datetime.fromisoformat(acc['check_in_date']))
            if acc.get('check_out_date'):
                dates.append(datetime.fromisoformat(acc['check_out_date']))
        
        # Collect from activities
        for activity in self.activities:
            if activity.get('start_datetime'):
                dates.append(datetime.fromisoformat(activity['start_datetime']))
            if activity.get('end_datetime'):
                dates.append(datetime.fromisoformat(activity['end_datetime']))
        
        # Collect from cruises
        for cruise in self.cruises:
            if cruise.get('departure_datetime'):
                dates.append(datetime.fromisoformat(cruise['departure_datetime']))
            if cruise.get('arrival_datetime'):
                dates.append(datetime.fromisoformat(cruise['arrival_datetime']))
        
        if not dates:
            return None, None
        
        return min(dates), max(dates)
    
    def get_total_cost(self) -> float:
        """Calculate total cost from all segments"""
        total = 0.0
        
        # Add costs from all segments
        for segment in self.transport_segments:
            total += segment.get('cost', 0.0)
        
        for acc in self.accommodations:
            total += acc.get('cost', 0.0)
        
        for activity in self.activities:
            total += activity.get('cost', 0.0)
        
        for cruise in self.cruises:
            total += cruise.get('cost', 0.0)
        
        # Use cost_info total if available and higher
        if self.cost_info and self.cost_info.total_cost > total:
            total = self.cost_info.total_cost
        
        return total
    
    @classmethod
    def from_json(cls, json_str: str) -> 'BookingInfo':
        """Create BookingInfo from JSON string"""
        try:
            data = json.loads(json_str)
            # Fix any fixable errors before creating the object
            data = cls._fix_booking_data(data)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Invalid JSON string: {json_str[:500]}...")
            raise
        except Exception as e:
            logger.error(f"Error parsing booking JSON: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    @classmethod
    def _fix_booking_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fix common fixable errors in booking data.
        This method handles data normalization and fixes common AI response issues.
        
        Raises:
            ValueError: If critical data is missing or unfixable
        """
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data)}")
        
        # Fix 1: Convert null list fields to empty lists
        list_fields = ['transport_segments', 'accommodations', 'activities', 'cruises', 'confirmation_numbers']
        for field in list_fields:
            if data.get(field) is None:
                data[field] = []
                logger.debug(f"Fixed: Converted null '{field}' to empty list")
        
        # Fix 2: Ensure status field has a valid default if missing or null
        if not data.get('status'):
            data['status'] = 'unknown'
            logger.debug("Fixed: Set missing/null status to 'unknown'")
        
        # Fix 3: Ensure cost_info has proper structure if present
        if data.get('cost_info'):
            cost_info = data['cost_info']
            if not isinstance(cost_info, dict):
                logger.warning(f"cost_info is not a dict: {type(cost_info)}, removing it")
                data['cost_info'] = None
            else:
                if cost_info.get('total_cost') is None:
                    cost_info['total_cost'] = 0.0
                    logger.debug("Fixed: Set null total_cost to 0.0")
                if cost_info.get('cost_breakdown') is None:
                    cost_info['cost_breakdown'] = {}
                    logger.debug("Fixed: Set null cost_breakdown to empty dict")
        
        # Fix 4: Convert single confirmation_number string to list
        if isinstance(data.get('confirmation_numbers'), str):
            data['confirmation_numbers'] = [data['confirmation_numbers']]
            logger.debug("Fixed: Converted single confirmation_number string to list")
        
        # Fix 5: Validate critical fields based on booking type
        if data.get('is_travel') is True and data.get('booking_type') is not None:
            # This is a booking email - no critical validation needed here
            # The validation will happen in validate_for_trip_detection()
            pass
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BookingInfo':
        """Create BookingInfo from dictionary"""
        # Convert string values to enums
        if data.get('booking_type'):
            try:
                data['booking_type'] = BookingType(data['booking_type'])
            except ValueError:
                logger.warning(f"Unknown booking type: {data['booking_type']}")
                data['booking_type'] = None
        
        if data.get('non_booking_type'):
            try:
                data['non_booking_type'] = NonBookingType(data['non_booking_type'])
            except ValueError:
                logger.warning(f"Unknown non-booking type: {data['non_booking_type']}")
                data['non_booking_type'] = None
        
        if data.get('status'):
            try:
                data['status'] = BookingStatus(data['status'])
            except ValueError:
                data['status'] = BookingStatus.CONFIRMED
        
        # Convert nested objects
        if data.get('cost_info'):
            cost_data = data['cost_info']
            # Ensure cost_breakdown is not None
            if cost_data.get('cost_breakdown') is None:
                cost_data['cost_breakdown'] = {}
            else:
                # Clean up cost_breakdown - ensure all values are numeric
                breakdown = cost_data.get('cost_breakdown', {})
                if isinstance(breakdown, dict):
                    cleaned_breakdown = {}
                    for key, value in breakdown.items():
                        # Only keep numeric values
                        if value is None:
                            cleaned_breakdown[key] = 0.0
                        elif isinstance(value, (int, float)):
                            cleaned_breakdown[key] = float(value)
                        elif isinstance(value, dict):
                            # Skip complex nested structures
                            logger.warning(f"Skipping complex cost_breakdown entry '{key}': {value}")
                            continue
                        else:
                            # Try to convert to float
                            try:
                                cleaned_breakdown[key] = float(value)
                            except (ValueError, TypeError):
                                logger.warning(f"Skipping non-numeric cost_breakdown entry '{key}': {value}")
                                continue
                    cost_data['cost_breakdown'] = cleaned_breakdown
            # Ensure total_cost is not None
            if cost_data.get('total_cost') is None:
                cost_data['total_cost'] = 0.0
            data['cost_info'] = CostInfo(**cost_data)
        
        if data.get('dates'):
            dates_data = data['dates']
            # Convert string dates to datetime
            for field in ['booking_date', 'travel_start_date', 'travel_end_date']:
                if dates_data.get(field) and isinstance(dates_data[field], str):
                    dates_data[field] = datetime.fromisoformat(dates_data[field])
            data['dates'] = BookingDates(**dates_data)
        
        if data.get('additional_info'):
            data['additional_info'] = AdditionalInfo(**data['additional_info'])
        
        return cls(**data)
    
    @classmethod
    def prepare_emails_for_trip_detection(cls, emails: List[Any]) -> tuple[List[Dict], List[tuple[Any, str]]]:
        """
        Prepare a list of emails for trip detection.
        
        Args:
            emails: List of Email objects with email_content
            
        Returns:
            Tuple of (valid_email_data, invalid_emails)
            - valid_email_data: List of dictionaries ready for TripDetector
            - invalid_emails: List of (email, reason) tuples for emails that failed validation
        """
        valid_email_data = []
        invalid_emails = []
        
        for email in emails:
            try:
                # Load booking info from email content
                booking_info = cls.from_email_content(email.email_content)
                if not booking_info:
                    invalid_emails.append((email, "No booking information"))
                    continue
                
                # Validate for trip detection
                is_valid, reason = booking_info.validate_for_trip_detection()
                if not is_valid:
                    invalid_emails.append((email, reason))
                    continue
                
                # Convert to format expected by TripDetector
                email_data = booking_info.to_email_data_dict(email)
                valid_email_data.append(email_data)
                
            except Exception as e:
                logger.error(f"Error processing email {email.email_id}: {e}")
                invalid_emails.append((email, f"Processing error: {str(e)}"))
        
        return valid_email_data, invalid_emails
    
    @classmethod
    def from_email_content(cls, email_content: Any) -> Optional['BookingInfo']:
        """Create BookingInfo from EmailContent database model"""
        if not email_content.extracted_booking_info:
            return None
        
        # Ensure email_content has email_id
        if not hasattr(email_content, 'email_id'):
            raise ValueError("EmailContent object must have email_id attribute")
        
        try:
            booking = cls.from_json(email_content.extracted_booking_info)
            booking.email_id = email_content.email_id
            booking.extracted_at = email_content.updated_at
            return booking
        except Exception as e:
            logger.error(f"Error creating BookingInfo from EmailContent for email {email_content.email_id}: {e}")
            return None
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
    
    def to_email_data_dict(self, email: Any) -> Dict[str, Any]:
        """Convert to dictionary format expected by TripDetector, including email metadata"""
        return {
            'email_id': email.email_id,
            'subject': email.subject,
            'sender': email.sender,
            'date': email.timestamp.isoformat() if email.timestamp else email.date,
            'classification': email.classification,
            'extracted_booking_info': self.to_dict()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = {
            'booking_type': self.booking_type.value if self.booking_type else None,
            'non_booking_type': self.non_booking_type.value if self.non_booking_type else None,
            'reason': self.reason,
            'status': self.status.value,
            'confirmation_numbers': self.confirmation_numbers,
            'original_booking_reference': self.original_booking_reference,
            'transport_segments': self.transport_segments,
            'accommodations': self.accommodations,
            'activities': self.activities,
            'cruises': self.cruises,
        }
        
        if self.cost_info:
            data['cost_info'] = self.cost_info.dict()
        
        if self.dates:
            dates_dict = self.dates.dict()
            # Convert datetime to ISO format strings
            for field in ['booking_date', 'travel_start_date', 'travel_end_date']:
                if dates_dict.get(field):
                    dates_dict[field] = dates_dict[field].isoformat()
            data['dates'] = dates_dict
        
        if self.additional_info:
            data['additional_info'] = self.additional_info.dict()
        
        return data