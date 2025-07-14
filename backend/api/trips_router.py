"""
Trip Management API Endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
from datetime import datetime
from backend.database.config import SessionLocal
from backend.database.models import Trip, TransportSegment, Accommodation, TourActivity, Cruise
from backend.services.trip_detection_service import TripDetectionService
from backend.services.email_booking_extraction_service import EmailBookingExtractionService

router = APIRouter()

# Global service instances
trip_detection_service = TripDetectionService()
booking_extraction_service = EmailBookingExtractionService()

@router.post("/extract-bookings")
async def start_booking_extraction(request: dict) -> Dict:
    """Start booking information extraction process (Step 1)"""
    try:
        date_range = request.get('date_range')
        email_ids = request.get('email_ids')  # Optional list of email IDs
        result = booking_extraction_service.start_extraction(date_range=date_range, email_ids=email_ids)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/extract-bookings/progress")
async def get_booking_extraction_progress() -> Dict:
    """Get current booking extraction progress"""
    try:
        return booking_extraction_service.get_extraction_progress()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/extract-bookings/stop")
async def stop_booking_extraction() -> Dict:
    """Stop ongoing booking extraction process"""
    try:
        message = booking_extraction_service.stop_extraction()
        return {"stopped": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detect")
async def start_trip_detection(request: dict) -> Dict:
    """Start trip detection process (Step 2) - requires booking extraction to be completed first"""
    try:
        date_range = request.get('date_range')
        result = trip_detection_service.start_detection(date_range)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/detection/progress")
async def get_detection_progress() -> Dict:
    """Get current trip detection progress"""
    try:
        return trip_detection_service.get_detection_progress()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detection/stop")
async def stop_detection() -> Dict:
    """Stop ongoing trip detection process"""
    try:
        message = trip_detection_service.stop_detection()
        return {"stopped": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detection/reset")
async def reset_trip_detection() -> Dict:
    """Reset trip detection status for all emails and clear all trips"""
    try:
        result = trip_detection_service.reset_trip_detection_status()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_trips(
    start_date: Optional[datetime] = Query(None, description="Filter trips starting after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter trips ending before this date")
) -> List[Dict]:
    """List all detected trips with summary information"""
    db = SessionLocal()
    try:
        query = db.query(Trip)
        
        # Apply date filters
        if start_date:
            query = query.filter(Trip.start_date >= start_date)
        if end_date:
            query = query.filter(Trip.end_date <= end_date)
        
        # Order by start date descending
        trips = query.order_by(Trip.start_date.desc()).all()
        
        # Build trip list with summary info
        trip_list = []
        for trip in trips:
            # Parse cities visited
            import json
            cities_visited = json.loads(trip.cities_visited) if trip.cities_visited else []
            
            # Count bookings and calculate status
            transport_count = db.query(TransportSegment).filter_by(trip_id=trip.id).count()
            accommodation_count = db.query(Accommodation).filter_by(trip_id=trip.id).count()
            tour_count = db.query(TourActivity).filter_by(trip_id=trip.id).count()
            cruise_count = db.query(Cruise).filter_by(trip_id=trip.id).count()
            
            # Check for cancellations
            has_cancellations = (
                db.query(TransportSegment).filter_by(trip_id=trip.id, status='cancelled').count() > 0 or
                db.query(Accommodation).filter_by(trip_id=trip.id, status='cancelled').count() > 0 or
                db.query(TourActivity).filter_by(trip_id=trip.id, status='cancelled').count() > 0 or
                db.query(Cruise).filter_by(trip_id=trip.id, status='cancelled').count() > 0
            )
            
            trip_dict = {
                'id': trip.id,
                'name': trip.name,
                'destination': trip.destination,
                'start_date': trip.start_date.isoformat() if trip.start_date else None,
                'end_date': trip.end_date.isoformat() if trip.end_date else None,
                'total_cost': trip.total_cost,
                'cities_visited': cities_visited,
                'booking_counts': {
                    'transport': transport_count,
                    'accommodation': accommodation_count,
                    'tours': tour_count,
                    'cruises': cruise_count,
                    'total': transport_count + accommodation_count + tour_count + cruise_count
                },
                'has_cancellations': has_cancellations,
                'created_at': trip.created_at.isoformat() if trip.created_at else None
            }
            trip_list.append(trip_dict)
        
        return trip_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/{trip_id}")
async def get_trip_details(trip_id: int) -> Dict:
    """Get detailed trip information including all bookings"""
    db = SessionLocal()
    try:
        # Get trip
        trip = db.query(Trip).filter_by(id=trip_id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        
        # Parse stored JSON fields
        import json
        cities_visited = json.loads(trip.cities_visited) if trip.cities_visited else []
        
        # Get all related bookings
        transport_segments = []
        for segment in db.query(TransportSegment).filter_by(trip_id=trip_id).all():
            # Get related emails
            email_ids = [link.email_id for link in segment.emails]
            
            transport_segments.append({
                'id': segment.id,
                'segment_type': segment.segment_type,
                'departure_location': segment.departure_location,
                'arrival_location': segment.arrival_location,
                'departure_datetime': segment.departure_datetime.isoformat(),
                'arrival_datetime': segment.arrival_datetime.isoformat(),
                'duration_minutes': segment.duration_minutes,
                'distance_km': segment.distance_km,
                'distance_type': segment.distance_type,
                'carrier_name': segment.carrier_name,
                'segment_number': segment.segment_number,
                'cost': segment.cost,
                'booking_platform': segment.booking_platform,
                'confirmation_number': segment.confirmation_number,
                'status': segment.status,
                'is_latest_version': segment.is_latest_version,
                'related_email_ids': email_ids
            })
        
        accommodations = []
        for accommodation in db.query(Accommodation).filter_by(trip_id=trip_id).all():
            email_ids = [link.email_id for link in accommodation.emails]
            
            accommodations.append({
                'id': accommodation.id,
                'property_name': accommodation.property_name,
                'check_in_date': accommodation.check_in_date.isoformat(),
                'check_out_date': accommodation.check_out_date.isoformat(),
                'address': accommodation.address,
                'city': accommodation.city,
                'country': accommodation.country,
                'cost': accommodation.cost,
                'booking_platform': accommodation.booking_platform,
                'confirmation_number': accommodation.confirmation_number,
                'status': accommodation.status,
                'is_latest_version': accommodation.is_latest_version,
                'related_email_ids': email_ids
            })
        
        tour_activities = []
        for tour in db.query(TourActivity).filter_by(trip_id=trip_id).all():
            email_ids = [link.email_id for link in tour.emails]
            
            tour_activities.append({
                'id': tour.id,
                'activity_name': tour.activity_name,
                'description': tour.description,
                'start_datetime': tour.start_datetime.isoformat(),
                'end_datetime': tour.end_datetime.isoformat(),
                'location': tour.location,
                'city': tour.city,
                'cost': tour.cost,
                'booking_platform': tour.booking_platform,
                'confirmation_number': tour.confirmation_number,
                'status': tour.status,
                'is_latest_version': tour.is_latest_version,
                'related_email_ids': email_ids
            })
        
        cruises = []
        for cruise in db.query(Cruise).filter_by(trip_id=trip_id).all():
            email_ids = [link.email_id for link in cruise.emails]
            itinerary = json.loads(cruise.itinerary) if cruise.itinerary else []
            
            cruises.append({
                'id': cruise.id,
                'cruise_line': cruise.cruise_line,
                'ship_name': cruise.ship_name,
                'departure_datetime': cruise.departure_datetime.isoformat(),
                'arrival_datetime': cruise.arrival_datetime.isoformat(),
                'itinerary': itinerary,
                'cost': cruise.cost,
                'booking_platform': cruise.booking_platform,
                'confirmation_number': cruise.confirmation_number,
                'status': cruise.status,
                'is_latest_version': cruise.is_latest_version,
                'related_email_ids': email_ids
            })
        
        # Calculate derived status
        all_bookings = transport_segments + accommodations + tour_activities + cruises
        has_cancellations = any(booking['status'] == 'cancelled' for booking in all_bookings)
        has_modifications = any(booking['status'] == 'modified' for booking in all_bookings)
        
        trip_status = 'confirmed'
        if has_cancellations:
            trip_status = 'has_cancellations'
        elif has_modifications:
            trip_status = 'has_modifications'
        
        # Build complete trip response
        trip_details = {
            'id': trip.id,
            'name': trip.name,
            'destination': trip.destination,
            'start_date': trip.start_date.isoformat() if trip.start_date else None,
            'end_date': trip.end_date.isoformat() if trip.end_date else None,
            'total_cost': trip.total_cost,
            'origin_city': trip.origin_city,
            'cities_visited': cities_visited,
            'description': trip.description,
            'notes': trip.notes,
            'trip_status': trip_status,
            'transport_segments': transport_segments,
            'accommodations': accommodations,
            'tour_activities': tour_activities,
            'cruises': cruises,
            'created_at': trip.created_at.isoformat() if trip.created_at else None,
            'updated_at': trip.updated_at.isoformat() if trip.updated_at else None
        }
        
        return trip_details
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.put("/{trip_id}")
async def update_trip(trip_id: int, trip_data: dict) -> Dict:
    """Update trip information (manual editing)"""
    db = SessionLocal()
    try:
        trip = db.query(Trip).filter_by(id=trip_id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        
        # Update allowed fields
        if 'name' in trip_data:
            trip.name = trip_data['name']
        if 'destination' in trip_data:
            trip.destination = trip_data['destination']
        if 'description' in trip_data:
            trip.description = trip_data['description']
        if 'notes' in trip_data:
            trip.notes = trip_data['notes']
        
        db.commit()
        
        return {"success": True, "message": "Trip updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()