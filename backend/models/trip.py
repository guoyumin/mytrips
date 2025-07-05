from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from enum import Enum

class TripType(str, Enum):
    FLIGHT = "flight"
    HOTEL = "hotel"
    TRAIN = "train"
    CAR_RENTAL = "car_rental"
    ACTIVITY = "activity"
    RESTAURANT = "restaurant"
    OTHER = "other"

class Location(BaseModel):
    city: str
    country: Optional[str] = None
    airport_code: Optional[str] = None
    coordinates: Optional[dict] = None

class TripSegment(BaseModel):
    type: TripType
    start_date: datetime
    end_date: Optional[datetime] = None
    origin: Optional[Location] = None
    destination: Optional[Location] = None
    provider: Optional[str] = None
    booking_reference: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    raw_email_id: Optional[str] = None

class Trip(BaseModel):
    id: Optional[str] = None
    name: str
    start_date: datetime
    end_date: datetime
    destinations: List[Location]
    segments: List[TripSegment]
    total_cost: Optional[float] = None
    currency: Optional[str] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    email_count: int = 0
    status: str = "confirmed"