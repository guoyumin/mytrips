"""
Trip domain model with business logic
"""
from pydantic import BaseModel, Field, validator, ValidationError
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
import json
import logging

from backend.database import models as db_models
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class Location(BaseModel):
    city: str
    country: Optional[str] = None
    airport_code: Optional[str] = None
    coordinates: Optional[dict] = None


class TransportSegment(BaseModel):
    segment_type: str
    departure_location: str
    arrival_location: str
    departure_datetime: datetime
    arrival_datetime: datetime
    carrier_name: Optional[str] = None
    segment_number: Optional[str] = None
    distance_km: Optional[float] = None
    distance_type: Optional[str] = None  # 'actual' or 'straight'
    cost: float = 0.0
    booking_platform: Optional[str] = None
    confirmation_number: Optional[str] = None
    status: str = "confirmed"
    is_latest_version: bool = True
    related_email_ids: List[str] = Field(default_factory=list)
    
    @validator('segment_type')
    def validate_segment_type(cls, v):
        allowed_types = ['flight', 'train', 'bus', 'ferry', 'car', 'other']
        if v.lower() not in allowed_types:
            logger.warning(f"Unknown segment type: {v}, using 'other'")
            return 'other'
        return v.lower()
    
    @validator('arrival_datetime')
    def validate_arrival_after_departure(cls, v, values):
        # Skip validation for cross-timezone travel
        # In cross-timezone scenarios, arrival time might appear earlier than departure time
        # Example: Tokyo 23:00 -> Los Angeles 16:00 (same day)
        return v
    
    @validator('distance_type')
    def validate_distance_type(cls, v):
        if v and v not in ['actual', 'straight']:
            raise ValueError('distance_type must be either "actual" or "straight"')
        return v
    
    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = ['confirmed', 'cancelled', 'modified', 'pending']
        if v.lower() not in allowed_statuses:
            raise ValueError(f'status must be one of {allowed_statuses}')
        return v.lower()
    
    def to_db_model(self, trip_id: int) -> db_models.TransportSegment:
        """Convert to database model"""
        return db_models.TransportSegment(
            trip_id=trip_id,
            segment_type=self.segment_type,
            departure_location=self.departure_location,
            arrival_location=self.arrival_location,
            departure_datetime=self.departure_datetime,
            arrival_datetime=self.arrival_datetime,
            duration_minutes=int((self.arrival_datetime - self.departure_datetime).total_seconds() / 60),
            distance_km=self.distance_km,
            distance_type=self.distance_type,
            carrier_name=self.carrier_name,
            segment_number=self.segment_number,
            cost=self.cost,
            booking_platform=self.booking_platform,
            confirmation_number=self.confirmation_number,
            status=self.status,
            is_latest_version=self.is_latest_version
        )
    
    @classmethod
    def from_db_model(cls, db_segment: db_models.TransportSegment) -> 'TransportSegment':
        """Create from database model"""
        return cls(
            segment_type=db_segment.segment_type,
            departure_location=db_segment.departure_location,
            arrival_location=db_segment.arrival_location,
            departure_datetime=db_segment.departure_datetime,
            arrival_datetime=db_segment.arrival_datetime,
            carrier_name=db_segment.carrier_name,
            segment_number=db_segment.segment_number,
            distance_km=db_segment.distance_km,
            distance_type=db_segment.distance_type,
            cost=db_segment.cost or 0.0,
            booking_platform=db_segment.booking_platform,
            confirmation_number=db_segment.confirmation_number,
            status=db_segment.status,
            is_latest_version=db_segment.is_latest_version,
            related_email_ids=[email.email_id for email in db_segment.emails]
        )


class Accommodation(BaseModel):
    property_name: str
    check_in_date: datetime
    check_out_date: datetime
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    cost: float = 0.0
    booking_platform: Optional[str] = None
    confirmation_number: Optional[str] = None
    status: str = "confirmed"
    is_latest_version: bool = True
    related_email_ids: List[str] = Field(default_factory=list)
    
    @validator('check_out_date')
    def validate_checkout_after_checkin(cls, v, values):
        # Keep validation for accommodations as they typically use local time
        # and check-out should always be after check-in
        if 'check_in_date' in values and v <= values['check_in_date']:
            raise ValueError('Check-out date must be after check-in date')
        return v
    
    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = ['confirmed', 'cancelled', 'modified', 'pending']
        if v.lower() not in allowed_statuses:
            raise ValueError(f'status must be one of {allowed_statuses}')
        return v.lower()
    
    def to_db_model(self, trip_id: int) -> db_models.Accommodation:
        """Convert to database model"""
        return db_models.Accommodation(
            trip_id=trip_id,
            property_name=self.property_name,
            check_in_date=self.check_in_date,
            check_out_date=self.check_out_date,
            address=self.address,
            city=self.city,
            country=self.country,
            cost=self.cost,
            booking_platform=self.booking_platform,
            confirmation_number=self.confirmation_number,
            status=self.status,
            is_latest_version=self.is_latest_version
        )
    
    @classmethod
    def from_db_model(cls, db_accommodation: db_models.Accommodation) -> 'Accommodation':
        """Create from database model"""
        return cls(
            property_name=db_accommodation.property_name,
            check_in_date=db_accommodation.check_in_date,
            check_out_date=db_accommodation.check_out_date,
            address=db_accommodation.address,
            city=db_accommodation.city,
            country=db_accommodation.country,
            cost=db_accommodation.cost or 0.0,
            booking_platform=db_accommodation.booking_platform,
            confirmation_number=db_accommodation.confirmation_number,
            status=db_accommodation.status,
            is_latest_version=db_accommodation.is_latest_version,
            related_email_ids=[email.email_id for email in db_accommodation.emails]
        )


class TourActivity(BaseModel):
    activity_name: str
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    description: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    cost: float = 0.0
    booking_platform: Optional[str] = None
    confirmation_number: Optional[str] = None
    status: str = "confirmed"
    is_latest_version: bool = True
    related_email_ids: List[str] = Field(default_factory=list)
    
    def to_db_model(self, trip_id: int) -> db_models.TourActivity:
        """Convert to database model"""
        # Default end_datetime to start_datetime + 2 hours if not provided
        end_datetime = self.end_datetime or (self.start_datetime + timedelta(hours=2))
        
        return db_models.TourActivity(
            trip_id=trip_id,
            activity_name=self.activity_name,
            description=self.description,
            start_datetime=self.start_datetime,
            end_datetime=end_datetime,
            location=self.location,
            city=self.city,
            cost=self.cost,
            booking_platform=self.booking_platform,
            confirmation_number=self.confirmation_number,
            status=self.status,
            is_latest_version=self.is_latest_version
        )
    
    @classmethod
    def from_db_model(cls, db_activity: db_models.TourActivity) -> 'TourActivity':
        """Create from database model"""
        return cls(
            activity_name=db_activity.activity_name,
            description=db_activity.description,
            start_datetime=db_activity.start_datetime,
            end_datetime=db_activity.end_datetime,
            location=db_activity.location,
            city=db_activity.city,
            cost=db_activity.cost or 0.0,
            booking_platform=db_activity.booking_platform,
            confirmation_number=db_activity.confirmation_number,
            status=db_activity.status,
            is_latest_version=db_activity.is_latest_version,
            related_email_ids=[email.email_id for email in db_activity.emails]
        )


class Cruise(BaseModel):
    cruise_line: str
    ship_name: Optional[str] = None
    departure_datetime: datetime
    arrival_datetime: datetime
    itinerary: List[str] = Field(default_factory=list)
    cost: float = 0.0
    booking_platform: Optional[str] = None
    confirmation_number: Optional[str] = None
    status: str = "confirmed"
    is_latest_version: bool = True
    related_email_ids: List[str] = Field(default_factory=list)
    
    def to_db_model(self, trip_id: int) -> db_models.Cruise:
        """Convert to database model"""
        return db_models.Cruise(
            trip_id=trip_id,
            cruise_line=self.cruise_line,
            ship_name=self.ship_name,
            departure_datetime=self.departure_datetime,
            arrival_datetime=self.arrival_datetime,
            itinerary=json.dumps(self.itinerary),
            cost=self.cost,
            booking_platform=self.booking_platform,
            confirmation_number=self.confirmation_number,
            status=self.status,
            is_latest_version=self.is_latest_version
        )
    
    @classmethod
    def from_db_model(cls, db_cruise: db_models.Cruise) -> 'Cruise':
        """Create from database model"""
        return cls(
            cruise_line=db_cruise.cruise_line,
            ship_name=db_cruise.ship_name,
            departure_datetime=db_cruise.departure_datetime,
            arrival_datetime=db_cruise.arrival_datetime,
            itinerary=json.loads(db_cruise.itinerary) if db_cruise.itinerary else [],
            cost=db_cruise.cost or 0.0,
            booking_platform=db_cruise.booking_platform,
            confirmation_number=db_cruise.confirmation_number,
            status=db_cruise.status,
            is_latest_version=db_cruise.is_latest_version,
            related_email_ids=[email.email_id for email in db_cruise.emails]
        )


class Trip(BaseModel):
    """Domain model for a single trip"""
    id: Optional[int] = None
    name: str
    destination: Optional[str] = None
    start_date: datetime
    end_date: datetime
    origin_city: str = "Zurich"
    cities_visited: List[str] = Field(default_factory=list)
    total_cost: float = 0.0
    transport_segments: List[TransportSegment] = Field(default_factory=list)
    accommodations: List[Accommodation] = Field(default_factory=list)
    tour_activities: List[TourActivity] = Field(default_factory=list)
    cruises: List[Cruise] = Field(default_factory=list)
    ai_analysis: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def calculate_total_cost(self) -> float:
        """Calculate total cost from all segments"""
        total = 0.0
        total += sum(s.cost for s in self.transport_segments)
        total += sum(a.cost for a in self.accommodations)
        total += sum(t.cost for t in self.tour_activities)
        total += sum(c.cost for c in self.cruises)
        return total
    
    def merge_with(self, other: 'Trip') -> 'Trip':
        """Merge another trip's data into this one"""
        # Update basic info
        self.end_date = max(self.end_date, other.end_date)
        
        # Merge cities visited
        for city in other.cities_visited:
            if city not in self.cities_visited:
                self.cities_visited.append(city)
        
        # Merge segments (avoiding duplicates based on confirmation numbers)
        existing_confirmations = {s.confirmation_number for s in self.transport_segments if s.confirmation_number}
        for segment in other.transport_segments:
            if not segment.confirmation_number or segment.confirmation_number not in existing_confirmations:
                self.transport_segments.append(segment)
        
        # Similarly for accommodations, activities, and cruises
        existing_acc_confirmations = {a.confirmation_number for a in self.accommodations if a.confirmation_number}
        for acc in other.accommodations:
            if not acc.confirmation_number or acc.confirmation_number not in existing_acc_confirmations:
                self.accommodations.append(acc)
        
        existing_act_confirmations = {t.confirmation_number for t in self.tour_activities if t.confirmation_number}
        for act in other.tour_activities:
            if not act.confirmation_number or act.confirmation_number not in existing_act_confirmations:
                self.tour_activities.append(act)
        
        existing_cruise_confirmations = {c.confirmation_number for c in self.cruises if c.confirmation_number}
        for cruise in other.cruises:
            if not cruise.confirmation_number or cruise.confirmation_number not in existing_cruise_confirmations:
                self.cruises.append(cruise)
        
        # Recalculate total cost
        self.total_cost = self.calculate_total_cost()
        
        return self
    
    @classmethod
    def _validate_json_schema(cls, data: Dict) -> None:
        """Validate JSON data against expected schema"""
        # Check required top-level fields
        required_fields = ['name', 'start_date', 'end_date']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Validate that at least one type of booking exists
        booking_types = ['transport_segments', 'accommodations', 'tour_activities', 'cruises']
        has_bookings = any(data.get(booking_type) for booking_type in booking_types)
        if not has_bookings:
            raise ValueError("Trip must have at least one booking (transport, accommodation, activity, or cruise)")
        
        # Validate dates
        try:
            start_date = datetime.fromisoformat(data['start_date']) if isinstance(data['start_date'], str) else data['start_date']
            end_date = datetime.fromisoformat(data['end_date']) if isinstance(data['end_date'], str) else data['end_date']
            if end_date < start_date:
                raise ValueError("Trip end_date must be after start_date")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid date format: {e}")
        
        # Validate transport segments
        for i, segment in enumerate(data.get('transport_segments', [])):
            required = ['segment_type', 'departure_location', 'arrival_location', 'departure_datetime', 'arrival_datetime']
            missing = [field for field in required if not segment.get(field)]
            if missing:
                raise ValueError(f"Transport segment {i} missing required fields: {missing}")
        
        # Validate accommodations
        for i, acc in enumerate(data.get('accommodations', [])):
            required = ['property_name', 'check_in_date', 'check_out_date']
            missing = [field for field in required if not acc.get(field)]
            if missing:
                raise ValueError(f"Accommodation {i} missing required fields: {missing}")
        
        # Validate activities
        for i, activity in enumerate(data.get('tour_activities', [])):
            required = ['activity_name', 'start_datetime']
            missing = [field for field in required if not activity.get(field)]
            if missing:
                raise ValueError(f"Tour activity {i} missing required fields: {missing}")
        
        # Validate cruises
        for i, cruise in enumerate(data.get('cruises', [])):
            required = ['cruise_line', 'departure_datetime', 'arrival_datetime']
            missing = [field for field in required if not cruise.get(field)]
            if missing:
                raise ValueError(f"Cruise {i} missing required fields: {missing}")
    
    @staticmethod
    def parse_json(json_str: str) -> Dict:
        """Parse and validate JSON string"""
        try:
            data = json.loads(json_str)
            if not isinstance(data, dict):
                raise ValueError("JSON must be an object, not an array or primitive")
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    
    @classmethod
    def from_json_string(cls, json_str: str) -> 'Trip':
        """Create Trip from JSON string"""
        data = cls.parse_json(json_str)
        return cls.from_json(data)
    
    @classmethod
    def from_json(cls, data: Dict) -> 'Trip':
        """Create Trip from JSON data with validation"""
        # Validate required fields
        cls._validate_json_schema(data)
        
        try:
            # Parse dates
            start_date = datetime.fromisoformat(data['start_date']) if isinstance(data['start_date'], str) else data['start_date']
            end_date = datetime.fromisoformat(data['end_date']) if isinstance(data['end_date'], str) else data['end_date']
            
            # Create segments with validation
            transport_segments = []
            for i, seg_data in enumerate(data.get('transport_segments', [])):
                try:
                    segment = TransportSegment(
                        segment_type=seg_data.get('segment_type', ''),
                        departure_location=seg_data.get('departure_location', ''),
                        arrival_location=seg_data.get('arrival_location', ''),
                        departure_datetime=datetime.fromisoformat(seg_data['departure_datetime']),
                        arrival_datetime=datetime.fromisoformat(seg_data['arrival_datetime']),
                        carrier_name=seg_data.get('carrier_name'),
                        segment_number=seg_data.get('segment_number'),
                        distance_km=seg_data.get('distance_km'),
                        distance_type=seg_data.get('distance_type'),
                        cost=seg_data.get('cost') or 0.0,
                        booking_platform=seg_data.get('booking_platform'),
                        confirmation_number=seg_data.get('confirmation_number'),
                        status=seg_data.get('status', 'confirmed'),
                        is_latest_version=seg_data.get('is_latest_version', True),
                        related_email_ids=seg_data.get('related_email_ids', [])
                    )
                    transport_segments.append(segment)
                except (ValueError, ValidationError) as e:
                    raise ValueError(f"Invalid transport segment {i}: {e}")
        
            # Create accommodations
            accommodations = []
            for i, acc_data in enumerate(data.get('accommodations', [])):
                try:
                    accommodation = Accommodation(
                        property_name=acc_data.get('property_name', ''),
                        check_in_date=datetime.fromisoformat(acc_data['check_in_date']),
                        check_out_date=datetime.fromisoformat(acc_data['check_out_date']),
                        address=acc_data.get('address'),
                        city=acc_data.get('city'),
                        country=acc_data.get('country'),
                        cost=acc_data.get('cost') or 0.0,
                        booking_platform=acc_data.get('booking_platform'),
                        confirmation_number=acc_data.get('confirmation_number'),
                        status=acc_data.get('status', 'confirmed'),
                        is_latest_version=acc_data.get('is_latest_version', True),
                        related_email_ids=acc_data.get('related_email_ids', [])
                    )
                    accommodations.append(accommodation)
                except (ValueError, ValidationError) as e:
                    raise ValueError(f"Invalid accommodation {i}: {e}")
            
            # Create activities
            tour_activities = []
            for i, act_data in enumerate(data.get('tour_activities', [])):
                try:
                    activity = TourActivity(
                        activity_name=act_data.get('activity_name', ''),
                        start_datetime=datetime.fromisoformat(act_data['start_datetime']),
                        end_datetime=datetime.fromisoformat(act_data['end_datetime']) if act_data.get('end_datetime') else None,
                        description=act_data.get('description'),
                        location=act_data.get('location'),
                        city=act_data.get('city'),
                        cost=act_data.get('cost') or 0.0,
                        booking_platform=act_data.get('booking_platform'),
                        confirmation_number=act_data.get('confirmation_number'),
                        status=act_data.get('status', 'confirmed'),
                        is_latest_version=act_data.get('is_latest_version', True),
                        related_email_ids=act_data.get('related_email_ids', [])
                    )
                    tour_activities.append(activity)
                except (ValueError, ValidationError) as e:
                    raise ValueError(f"Invalid tour activity {i}: {e}")
        
            # Create cruises
            cruises = []
            for i, cruise_data in enumerate(data.get('cruises', [])):
                try:
                    cruise = Cruise(
                        cruise_line=cruise_data.get('cruise_line', ''),
                        ship_name=cruise_data.get('ship_name'),
                        departure_datetime=datetime.fromisoformat(cruise_data['departure_datetime']),
                        arrival_datetime=datetime.fromisoformat(cruise_data['arrival_datetime']),
                        itinerary=cruise_data.get('itinerary', []),
                        cost=cruise_data.get('cost') or 0.0,
                        booking_platform=cruise_data.get('booking_platform'),
                        confirmation_number=cruise_data.get('confirmation_number'),
                        status=cruise_data.get('status', 'confirmed'),
                        is_latest_version=cruise_data.get('is_latest_version', True),
                        related_email_ids=cruise_data.get('related_email_ids', [])
                    )
                    cruises.append(cruise)
                except (ValueError, ValidationError) as e:
                    raise ValueError(f"Invalid cruise {i}: {e}")
        
            trip = cls(
                name=data['name'],
                destination=data.get('destination'),
                start_date=start_date,
                end_date=end_date,
                cities_visited=data.get('cities_visited', []),
                total_cost=data.get('total_cost', 0.0),
                transport_segments=transport_segments,
                accommodations=accommodations,
                tour_activities=tour_activities,
                cruises=cruises,
                ai_analysis=data.get('ai_analysis', {})
            )
            
            # Calculate total cost if not provided
            if not trip.total_cost:
                trip.total_cost = trip.calculate_total_cost()
            
            return trip
            
        except ValidationError as e:
            raise ValueError(f"Trip validation failed: {e}")
        except Exception as e:
            logger.error(f"Failed to create Trip from JSON: {e}")
            raise ValueError(f"Failed to create Trip from JSON: {e}")
    
    def to_db_model(self) -> db_models.Trip:
        """Convert to database model"""
        return db_models.Trip(
            id=self.id,
            name=self.name,
            destination=self.destination,
            start_date=self.start_date.date() if hasattr(self.start_date, 'date') else self.start_date,
            end_date=self.end_date.date() if hasattr(self.end_date, 'date') else self.end_date,
            total_cost=self.total_cost,
            origin_city=self.origin_city,
            cities_visited=json.dumps(self.cities_visited),
            ai_analysis=json.dumps(self.ai_analysis)
        )
    
    @classmethod
    def from_db_model(cls, db_trip: db_models.Trip) -> 'Trip':
        """Create from database model with all relationships"""
        # Parse dates
        start_date = datetime.combine(db_trip.start_date, datetime.min.time()) if db_trip.start_date else None
        end_date = datetime.combine(db_trip.end_date, datetime.min.time()) if db_trip.end_date else None
        
        # Convert segments
        transport_segments = [TransportSegment.from_db_model(seg) for seg in db_trip.transport_segments]
        accommodations = [Accommodation.from_db_model(acc) for acc in db_trip.accommodations]
        tour_activities = [TourActivity.from_db_model(act) for act in db_trip.tour_activities]
        cruises = [Cruise.from_db_model(cruise) for cruise in db_trip.cruises]
        
        return cls(
            id=db_trip.id,
            name=db_trip.name,
            destination=db_trip.destination,
            start_date=start_date,
            end_date=end_date,
            origin_city=db_trip.origin_city,
            cities_visited=json.loads(db_trip.cities_visited) if db_trip.cities_visited else [],
            total_cost=db_trip.total_cost or 0.0,
            transport_segments=transport_segments,
            accommodations=accommodations,
            tour_activities=tour_activities,
            cruises=cruises,
            ai_analysis=json.loads(db_trip.ai_analysis) if db_trip.ai_analysis else {},
            created_at=db_trip.created_at,
            updated_at=db_trip.updated_at
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'destination': self.destination,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'origin_city': self.origin_city,
            'cities_visited': self.cities_visited,
            'total_cost': self.total_cost,
            'transport_segments': [seg.dict() for seg in self.transport_segments],
            'accommodations': [acc.dict() for acc in self.accommodations],
            'tour_activities': [act.dict() for act in self.tour_activities],
            'cruises': [cruise.dict() for cruise in self.cruises],
            'ai_analysis': self.ai_analysis
        }