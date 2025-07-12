"""
Trip Repository - handles all Trip persistence operations
"""
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Set
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from backend.database import models as db_models
from backend.models.trip import Trip, TransportSegment, Accommodation, TourActivity, Cruise

logger = logging.getLogger(__name__)


class TripRepository:
    """Repository for Trip domain model persistence"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def find_by_id(self, trip_id: int) -> Optional[Trip]:
        """Find a trip by ID"""
        db_trip = self.session.query(db_models.Trip).filter_by(id=trip_id).first()
        if db_trip:
            return Trip.from_db_model(db_trip)
        return None
    
    def find_all(self) -> List[Trip]:
        """Get all trips"""
        db_trips = self.session.query(db_models.Trip).all()
        return [Trip.from_db_model(db_trip) for db_trip in db_trips]
    
    def find_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Trip]:
        """Find trips within a date range"""
        db_trips = self.session.query(db_models.Trip).filter(
            and_(
                db_models.Trip.start_date >= start_date.date(),
                db_models.Trip.end_date <= end_date.date()
            )
        ).all()
        return [Trip.from_db_model(db_trip) for db_trip in db_trips]
    
    def find_overlapping_trips(self, start_date: datetime, end_date: datetime) -> List[Trip]:
        """Find trips that overlap with the given date range"""
        db_trips = self.session.query(db_models.Trip).filter(
            or_(
                # Trip starts within the range
                and_(
                    db_models.Trip.start_date >= start_date.date(),
                    db_models.Trip.start_date <= end_date.date()
                ),
                # Trip ends within the range
                and_(
                    db_models.Trip.end_date >= start_date.date(),
                    db_models.Trip.end_date <= end_date.date()
                ),
                # Trip spans the entire range
                and_(
                    db_models.Trip.start_date <= start_date.date(),
                    db_models.Trip.end_date >= end_date.date()
                )
            )
        ).all()
        return [Trip.from_db_model(db_trip) for db_trip in db_trips]
    
    def replace_all_trips(self, trips: List[Trip]) -> int:
        """
        Replace all existing trips with new ones.
        This is used when AI detection returns a complete set of trips.
        
        Args:
            trips: List of Trip domain objects to save
            
        Returns:
            Number of trips saved
        """
        try:
            # Delete all existing trips
            self.delete_all()
            
            # Save all new trips
            saved_count = 0
            for trip in trips:
                self.save(trip)
                saved_count += 1
            
            self.session.commit()
            logger.info(f"Replaced all trips. Saved {saved_count} new trips.")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error replacing all trips: {e}")
            self.session.rollback()
            raise
    
    def save(self, trip: Trip) -> Trip:
        """Save or update a trip"""
        try:
            # Convert to database model
            db_trip = trip.to_db_model()
            
            if trip.id:
                # Update existing trip
                existing_trip = self.session.query(db_models.Trip).filter_by(id=trip.id).first()
                if existing_trip:
                    # Update fields
                    existing_trip.name = db_trip.name
                    existing_trip.destination = db_trip.destination
                    existing_trip.start_date = db_trip.start_date
                    existing_trip.end_date = db_trip.end_date
                    existing_trip.total_cost = db_trip.total_cost
                    existing_trip.origin_city = db_trip.origin_city
                    existing_trip.cities_visited = db_trip.cities_visited
                    existing_trip.ai_analysis = db_trip.ai_analysis
                    db_trip = existing_trip
                else:
                    # Trip with ID not found, create new
                    self.session.add(db_trip)
            else:
                # Create new trip
                self.session.add(db_trip)
            
            self.session.flush()  # Get the ID if it's a new trip
            
            # Save segments with relationships
            self._save_transport_segments(db_trip.id, trip.transport_segments)
            self._save_accommodations(db_trip.id, trip.accommodations)
            self._save_tour_activities(db_trip.id, trip.tour_activities)
            self._save_cruises(db_trip.id, trip.cruises)
            
            self.session.commit()
            
            # Return the saved trip with updated ID
            trip.id = db_trip.id
            return trip
            
        except Exception as e:
            logger.error(f"Error saving trip: {e}")
            self.session.rollback()
            raise
    
    def delete(self, trip_id: int) -> bool:
        """Delete a trip and all its related data"""
        try:
            db_trip = self.session.query(db_models.Trip).filter_by(id=trip_id).first()
            if not db_trip:
                return False
            
            # Delete related records (cascade should handle this, but being explicit)
            self.session.query(db_models.TransportSegment).filter_by(trip_id=trip_id).delete()
            self.session.query(db_models.Accommodation).filter_by(trip_id=trip_id).delete()
            self.session.query(db_models.TourActivity).filter_by(trip_id=trip_id).delete()
            self.session.query(db_models.Cruise).filter_by(trip_id=trip_id).delete()
            
            # Delete the trip
            self.session.delete(db_trip)
            self.session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error deleting trip {trip_id}: {e}")
            self.session.rollback()
            return False
    
    def delete_all(self) -> int:
        """Delete all trips. Returns count of deleted trips."""
        try:
            count = self.session.query(db_models.Trip).count()
            
            # Delete all related records
            self.session.query(db_models.EmailTransportSegment).delete()
            self.session.query(db_models.EmailAccommodation).delete()
            self.session.query(db_models.EmailTourActivity).delete()
            self.session.query(db_models.EmailCruise).delete()
            
            self.session.query(db_models.TransportSegment).delete()
            self.session.query(db_models.Accommodation).delete()
            self.session.query(db_models.TourActivity).delete()
            self.session.query(db_models.Cruise).delete()
            
            # Delete all trips
            self.session.query(db_models.Trip).delete()
            self.session.commit()
            
            return count
            
        except Exception as e:
            logger.error(f"Error deleting all trips: {e}")
            self.session.rollback()
            raise
    
    def find_by_confirmation_number(self, confirmation_number: str) -> List[Trip]:
        """Find trips containing a specific confirmation number"""
        trips = []
        
        # Search in transport segments
        segments = self.session.query(db_models.TransportSegment).filter_by(
            confirmation_number=confirmation_number
        ).all()
        for segment in segments:
            if segment.trip and segment.trip.id not in [t.id for t in trips]:
                trips.append(Trip.from_db_model(segment.trip))
        
        # Search in accommodations
        accommodations = self.session.query(db_models.Accommodation).filter_by(
            confirmation_number=confirmation_number
        ).all()
        for acc in accommodations:
            if acc.trip and acc.trip.id not in [t.id for t in trips]:
                trips.append(Trip.from_db_model(acc.trip))
        
        # Search in activities
        activities = self.session.query(db_models.TourActivity).filter_by(
            confirmation_number=confirmation_number
        ).all()
        for activity in activities:
            if activity.trip and activity.trip.id not in [t.id for t in trips]:
                trips.append(Trip.from_db_model(activity.trip))
        
        # Search in cruises
        cruises = self.session.query(db_models.Cruise).filter_by(
            confirmation_number=confirmation_number
        ).all()
        for cruise in cruises:
            if cruise.trip and cruise.trip.id not in [t.id for t in trips]:
                trips.append(Trip.from_db_model(cruise.trip))
        
        return trips
    
    def _save_transport_segments(self, trip_id: int, segments: List[TransportSegment]):
        """Save transport segments for a trip"""
        # Delete existing segments
        self.session.query(db_models.TransportSegment).filter_by(trip_id=trip_id).delete()
        
        # Add new segments
        for segment in segments:
            db_segment = segment.to_db_model(trip_id)
            self.session.add(db_segment)
            self.session.flush()
            
            # Add email relationships
            self._add_email_relationships(
                db_models.EmailTransportSegment,
                'transport_segment_id',
                db_segment.id,
                segment.related_email_ids
            )
    
    def _save_accommodations(self, trip_id: int, accommodations: List[Accommodation]):
        """Save accommodations for a trip"""
        # Delete existing accommodations
        self.session.query(db_models.Accommodation).filter_by(trip_id=trip_id).delete()
        
        # Add new accommodations
        for acc in accommodations:
            db_acc = acc.to_db_model(trip_id)
            self.session.add(db_acc)
            self.session.flush()
            
            # Add email relationships
            self._add_email_relationships(
                db_models.EmailAccommodation,
                'accommodation_id',
                db_acc.id,
                acc.related_email_ids
            )
    
    def _save_tour_activities(self, trip_id: int, activities: List[TourActivity]):
        """Save tour activities for a trip"""
        # Delete existing activities
        self.session.query(db_models.TourActivity).filter_by(trip_id=trip_id).delete()
        
        # Add new activities
        for activity in activities:
            db_activity = activity.to_db_model(trip_id)
            self.session.add(db_activity)
            self.session.flush()
            
            # Add email relationships
            self._add_email_relationships(
                db_models.EmailTourActivity,
                'tour_activity_id',
                db_activity.id,
                activity.related_email_ids
            )
    
    def _save_cruises(self, trip_id: int, cruises: List[Cruise]):
        """Save cruises for a trip"""
        # Delete existing cruises
        self.session.query(db_models.Cruise).filter_by(trip_id=trip_id).delete()
        
        # Add new cruises
        for cruise in cruises:
            db_cruise = cruise.to_db_model(trip_id)
            self.session.add(db_cruise)
            self.session.flush()
            
            # Add email relationships
            self._add_email_relationships(
                db_models.EmailCruise,
                'cruise_id',
                db_cruise.id,
                cruise.related_email_ids
            )
    
    def _add_email_relationships(self, relationship_model, id_field: str, entity_id: int, email_ids: List[str]):
        """Add email relationships for an entity"""
        # Remove duplicates
        unique_email_ids = list(set(email_ids))
        
        for email_id in unique_email_ids:
            # Check if email exists
            email_exists = self.session.query(db_models.Email).filter_by(email_id=email_id).first()
            if email_exists:
                relationship_data = {
                    'email_id': email_id,
                    id_field: entity_id
                }
                
                # Check if relationship already exists
                existing = self.session.query(relationship_model).filter_by(**relationship_data).first()
                if not existing:
                    relationship = relationship_model(**relationship_data)
                    self.session.add(relationship)
    
    def get_statistics(self) -> Dict:
        """Get trip statistics"""
        total_trips = self.session.query(func.count(db_models.Trip.id)).scalar()
        
        # Get trips by month
        trips_by_month = self.session.query(
            func.strftime('%Y-%m', db_models.Trip.start_date).label('month'),
            func.count(db_models.Trip.id).label('count')
        ).group_by('month').all()
        
        # Get total costs
        total_cost = self.session.query(func.sum(db_models.Trip.total_cost)).scalar() or 0
        
        # Get segment counts
        transport_count = self.session.query(func.count(db_models.TransportSegment.id)).scalar()
        accommodation_count = self.session.query(func.count(db_models.Accommodation.id)).scalar()
        activity_count = self.session.query(func.count(db_models.TourActivity.id)).scalar()
        cruise_count = self.session.query(func.count(db_models.Cruise.id)).scalar()
        
        return {
            'total_trips': total_trips,
            'trips_by_month': [{'month': month, 'count': count} for month, count in trips_by_month],
            'total_cost': total_cost,
            'segment_counts': {
                'transport': transport_count,
                'accommodation': accommodation_count,
                'activity': activity_count,
                'cruise': cruise_count
            }
        }
    
    @staticmethod
    def merge_trip_data(existing_data: List[Dict], new_data: List[Dict]) -> List[Dict]:
        """
        Merge trip data dictionaries before converting to domain objects.
        Used when AI returns updated trip data that needs to be merged with existing trips.
        
        Args:
            existing_data: List of existing trip dictionaries
            new_data: List of new/updated trip dictionaries from AI
            
        Returns:
            Merged list of trip dictionaries
        """
        try:
            # Create a map of existing trips by name for easy lookup
            existing_trip_map = {}
            for trip in existing_data:
                trip_name = trip.get('name', 'Unknown')
                existing_trip_map[trip_name] = trip
            
            # Start with all existing trips
            merged_trips = existing_data.copy()
            
            # Add or update with new trips
            for new_trip in new_data:
                new_trip_name = new_trip.get('name', 'Unknown')
                
                if new_trip_name in existing_trip_map:
                    # This trip exists, replace it with the updated version
                    for i, trip in enumerate(merged_trips):
                        if trip.get('name') == new_trip_name:
                            merged_trips[i] = new_trip
                            logger.info(f"Updated existing trip: {new_trip_name}")
                            break
                else:
                    # This is a new trip, add it
                    merged_trips.append(new_trip)
                    logger.info(f"Added new trip: {new_trip_name}")
            
            logger.info(f"Trip data merge completed: {len(existing_data)} existing + {len(new_data)} new → {len(merged_trips)} total")
            return merged_trips
            
        except Exception as e:
            logger.error(f"Error in trip data merge, falling back to existing trips: {e}")
            return existing_data