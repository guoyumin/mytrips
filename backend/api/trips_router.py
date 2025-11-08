"""
Trip Management API Endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
from datetime import datetime, time, timedelta
from sqlalchemy import func, extract
from collections import defaultdict
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

@router.get("/timeline")
async def get_timeline(
    start_date: Optional[datetime] = Query(None, description="Filter activities starting after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter activities ending before this date")
) -> Dict:
    """Get all activities in chronological order for timeline view with trip information"""
    db = SessionLocal()
    try:
        activities = []
        
        # First get all trips to create a mapping
        trips_map = {}
        trips = db.query(Trip).all()
        for trip in trips:
            trips_map[trip.id] = {
                'id': trip.id,
                'name': trip.name,
                'destination': trip.destination,
                'start_date': trip.start_date.isoformat() if trip.start_date else None,
                'end_date': trip.end_date.isoformat() if trip.end_date else None
            }
        
        # Get all transport segments
        query = db.query(TransportSegment)
        if start_date:
            query = query.filter(TransportSegment.departure_datetime >= start_date)
        if end_date:
            query = query.filter(TransportSegment.departure_datetime <= end_date)
        
        for segment in query.all():
            activities.append({
                'id': f'transport_{segment.id}',
                'type': segment.segment_type or 'flight',
                'datetime': segment.departure_datetime.isoformat(),
                'airline_code': segment.carrier_name,
                'flight_number': segment.segment_number,
                'departure_location': segment.departure_location,
                'arrival_location': segment.arrival_location,
                'arrival_datetime': segment.arrival_datetime.isoformat() if segment.arrival_datetime else None,
                'confirmation_number': segment.confirmation_number,
                'status': segment.status,
                'trip_id': segment.trip_id
            })
        
        # Get all accommodations (check-in and check-out as separate events)
        query = db.query(Accommodation)
        if start_date:
            query = query.filter(Accommodation.check_in_date >= start_date.date())
        if end_date:
            query = query.filter(Accommodation.check_out_date <= end_date.date())
        
        for accommodation in query.all():
            # Check-in event
            if accommodation.check_in_date:
                check_in_datetime = datetime.combine(accommodation.check_in_date, time(14, 0))
                activities.append({
                    'id': f'hotel_checkin_{accommodation.id}',
                    'type': 'hotel',
                    'check_type': 'check_in',
                    'datetime': check_in_datetime.isoformat(),
                    'property_name': accommodation.property_name,
                    'address': accommodation.address,
                    'city': accommodation.city,
                    'country': accommodation.country,
                    'confirmation_number': accommodation.confirmation_number,
                    'status': accommodation.status,
                    'trip_id': accommodation.trip_id
                })
            
            # Check-out event
            if accommodation.check_out_date:
                check_out_datetime = datetime.combine(accommodation.check_out_date, time(12, 0))
                activities.append({
                    'id': f'hotel_checkout_{accommodation.id}',
                    'type': 'hotel',
                    'check_type': 'check_out',
                    'datetime': check_out_datetime.isoformat(),
                    'property_name': accommodation.property_name,
                    'address': accommodation.address,
                    'city': accommodation.city,
                    'country': accommodation.country,
                    'confirmation_number': accommodation.confirmation_number,
                    'status': accommodation.status,
                    'trip_id': accommodation.trip_id
                })
        
        # Get all tour activities
        query = db.query(TourActivity)
        if start_date:
            query = query.filter(TourActivity.start_datetime >= start_date)
        if end_date:
            query = query.filter(TourActivity.end_datetime <= end_date)
        
        for tour in query.all():
            activities.append({
                'id': f'tour_{tour.id}',
                'type': 'tour',
                'datetime': tour.start_datetime.isoformat() if tour.start_datetime else None,
                'activity_name': tour.activity_name,
                'description': tour.description,
                'location': tour.location,
                'city': tour.city,
                'confirmation_number': tour.confirmation_number,
                'status': tour.status,
                'trip_id': tour.trip_id
            })
        
        # Get all cruises
        query = db.query(Cruise)
        if start_date:
            query = query.filter(Cruise.departure_datetime >= start_date)
        if end_date:
            query = query.filter(Cruise.arrival_datetime <= end_date)
        
        for cruise in query.all():
            activities.append({
                'id': f'cruise_{cruise.id}',
                'type': 'cruise',
                'datetime': cruise.departure_datetime.isoformat() if cruise.departure_datetime else None,
                'cruise_line': cruise.cruise_line,
                'ship_name': cruise.ship_name,
                'departure_port': cruise.departure_port,
                'arrival_port': cruise.arrival_port,
                'confirmation_number': cruise.confirmation_number,
                'status': cruise.status,
                'trip_id': cruise.trip_id
            })
        
        # Sort all activities by datetime in descending order (newest first)
        activities.sort(key=lambda x: x.get('datetime', ''), reverse=True)
        
        # Filter out activities with invalid status
        activities = [a for a in activities if a.get('status') != 'cancelled']
        
        return {
            'activities': activities,
            'trips': trips_map
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/statistics")
async def get_travel_statistics(
    year: Optional[int] = Query(None, description="Filter statistics by year")
) -> Dict:
    """Get comprehensive travel statistics"""
    db = SessionLocal()
    try:
        # Build base queries with optional year filter
        trips_query = db.query(Trip)
        transport_query = db.query(TransportSegment).filter(TransportSegment.status != 'cancelled')
        accommodation_query = db.query(Accommodation).filter(Accommodation.status != 'cancelled')
        tour_query = db.query(TourActivity).filter(TourActivity.status != 'cancelled')
        cruise_query = db.query(Cruise).filter(Cruise.status != 'cancelled')
        
        if year:
            # Filter by year
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
            
            trips_query = trips_query.filter(
                Trip.start_date >= start_date,
                Trip.start_date <= end_date
            )
            transport_query = transport_query.filter(
                TransportSegment.departure_datetime >= start_date,
                TransportSegment.departure_datetime <= end_date
            )
            accommodation_query = accommodation_query.filter(
                Accommodation.check_in_date >= start_date.date(),
                Accommodation.check_in_date <= end_date.date()
            )
            tour_query = tour_query.filter(
                TourActivity.start_datetime >= start_date,
                TourActivity.start_datetime <= end_date
            )
            cruise_query = cruise_query.filter(
                Cruise.departure_datetime >= start_date,
                Cruise.departure_datetime <= end_date
            )
        
        # Basic counts
        total_trips = trips_query.count()
        total_cost = db.query(func.sum(Trip.total_cost)).scalar() or 0
        
        # Transport statistics
        transport_segments = transport_query.all()
        total_flights = sum(1 for t in transport_segments if t.segment_type == 'flight')
        total_trains = sum(1 for t in transport_segments if t.segment_type == 'train')
        total_distance = sum(t.distance_km or 0 for t in transport_segments)
        flight_distance = sum(t.distance_km or 0 for t in transport_segments if t.segment_type == 'flight')
        train_distance = sum(t.distance_km or 0 for t in transport_segments if t.segment_type == 'train')
        
        # Accommodation statistics
        accommodations = accommodation_query.all()
        hotel_nights = sum(
            (acc.check_out_date - acc.check_in_date).days 
            for acc in accommodations 
            if acc.check_out_date and acc.check_in_date
        )
        
        # Countries and cities visited
        countries = set()
        cities = set()
        
        # From accommodations
        for acc in accommodations:
            if acc.country:
                countries.add(acc.country)
            if acc.city:
                cities.add(acc.city)
        
        # From transport segments
        for seg in transport_segments:
            # Parse locations to extract cities/countries
            if seg.departure_location:
                parts = seg.departure_location.split(',')
                if len(parts) > 1:
                    cities.add(parts[0].strip())
            if seg.arrival_location:
                parts = seg.arrival_location.split(',')
                if len(parts) > 1:
                    cities.add(parts[0].strip())
        
        # From trips
        trips = trips_query.all()
        for trip in trips:
            if trip.cities_visited:
                import json
                try:
                    visited = json.loads(trip.cities_visited)
                    cities.update(visited)
                except:
                    pass
        
        # Get available years for filter
        years_with_trips = db.query(
            extract('year', Trip.start_date).label('year')
        ).distinct().order_by('year').all()
        available_years = [y.year for y in years_with_trips if y.year]
        
        # Transport breakdown by type
        transport_breakdown = defaultdict(lambda: {'count': 0, 'distance': 0})
        for seg in transport_segments:
            seg_type = seg.segment_type or 'other'
            transport_breakdown[seg_type]['count'] += 1
            transport_breakdown[seg_type]['distance'] += seg.distance_km or 0
        
        # Top destinations (by frequency)
        destination_count = defaultdict(int)
        for trip in trips:
            if trip.destination:
                destination_count[trip.destination] += 1
        
        top_destinations = sorted(
            destination_count.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        # Monthly distribution
        monthly_trips = defaultdict(int)
        for trip in trips:
            if trip.start_date:
                month_key = trip.start_date.strftime('%Y-%m')
                monthly_trips[month_key] += 1
        
        # Build response
        statistics = {
            'summary': {
                'total_trips': total_trips,
                'total_cost': round(total_cost, 2),
                'total_flights': total_flights,
                'total_trains': total_trains,
                'total_distance': round(total_distance, 0),
                'flight_distance': round(flight_distance, 0),
                'train_distance': round(train_distance, 0),
                'hotel_nights': hotel_nights,
                'countries_visited': len(countries),
                'cities_visited': len(cities),
                'countries_list': sorted(list(countries)),
                'cities_list': sorted(list(cities))
            },
            'transport_breakdown': dict(transport_breakdown),
            'top_destinations': [
                {'destination': dest, 'count': count} 
                for dest, count in top_destinations
            ],
            'monthly_distribution': dict(monthly_trips),
            'available_years': available_years,
            'current_filter': {
                'year': year,
                'description': f"Year {year}" if year else "All Time"
            }
        }
        
        return statistics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/statistics/flights")
async def get_flight_statistics_detail(
    year: Optional[int] = Query(None, description="Filter by year")
) -> Dict:
    """Get detailed flight statistics"""
    db = SessionLocal()
    try:
        query = db.query(TransportSegment).filter(
            TransportSegment.segment_type == 'flight',
            TransportSegment.status != 'cancelled'
        )
        
        if year:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
            query = query.filter(
                TransportSegment.departure_datetime >= start_date,
                TransportSegment.departure_datetime <= end_date
            )
        
        flights = query.order_by(TransportSegment.departure_datetime.desc()).all()
        
        # Airline statistics
        airline_stats = defaultdict(lambda: {'count': 0, 'distance': 0, 'routes': set()})
        route_stats = defaultdict(int)
        monthly_flights = defaultdict(int)
        class_distribution = defaultdict(int)
        
        flight_details = []
        total_distance = 0
        
        for flight in flights:
            # Add to flight details
            flight_dict = {
                'id': flight.id,
                'date': flight.departure_datetime.isoformat(),
                'flight_number': f"{flight.carrier_name or ''} {flight.segment_number or ''}".strip(),
                'route': f"{flight.departure_location} → {flight.arrival_location}",
                'distance': flight.distance_km or 0,
                'duration': flight.duration_minutes,
                'cost': flight.cost or 0,
                'confirmation': flight.confirmation_number,
                'status': flight.status
            }
            flight_details.append(flight_dict)
            
            # Aggregate statistics
            if flight.carrier_name:
                airline = flight.carrier_name.split()[0] if flight.carrier_name else 'Unknown'
                airline_stats[airline]['count'] += 1
                airline_stats[airline]['distance'] += flight.distance_km or 0
                route = f"{flight.departure_location} - {flight.arrival_location}"
                airline_stats[airline]['routes'].add(route)
            
            # Route statistics
            route_key = f"{flight.departure_location} → {flight.arrival_location}"
            route_stats[route_key] += 1
            
            # Monthly distribution
            month_key = flight.departure_datetime.strftime('%Y-%m')
            monthly_flights[month_key] += 1
            
            total_distance += flight.distance_km or 0
        
        # Convert sets to lists for JSON serialization
        for airline in airline_stats:
            airline_stats[airline]['routes'] = list(airline_stats[airline]['routes'])
        
        # Top routes
        top_routes = sorted(route_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'summary': {
                'total_flights': len(flights),
                'total_distance': round(total_distance, 0),
                'average_distance': round(total_distance / len(flights), 0) if flights else 0,
                'total_cost': sum(f.cost or 0 for f in flights),
                'airlines_used': len(airline_stats)
            },
            'airline_breakdown': dict(airline_stats),
            'top_routes': [{'route': route, 'count': count} for route, count in top_routes],
            'monthly_distribution': dict(monthly_flights),
            'recent_flights': flight_details[:20],  # Last 20 flights
            'all_flights': flight_details
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/statistics/hotels")
async def get_hotel_statistics_detail(
    year: Optional[int] = Query(None, description="Filter by year")
) -> Dict:
    """Get detailed hotel statistics"""
    db = SessionLocal()
    try:
        query = db.query(Accommodation).filter(
            Accommodation.status != 'cancelled'
        )
        
        if year:
            start_date = datetime(year, 1, 1).date()
            end_date = datetime(year, 12, 31).date()
            query = query.filter(
                Accommodation.check_in_date >= start_date,
                Accommodation.check_in_date <= end_date
            )
        
        hotels = query.order_by(Accommodation.check_in_date.desc()).all()
        
        # City statistics
        city_stats = defaultdict(lambda: {'count': 0, 'nights': 0, 'properties': set()})
        property_stats = defaultdict(int)
        monthly_nights = defaultdict(int)
        
        hotel_details = []
        total_nights = 0
        total_cost = 0
        
        for hotel in hotels:
            nights = 0
            if hotel.check_out_date and hotel.check_in_date:
                nights = (hotel.check_out_date - hotel.check_in_date).days
            
            # Add to hotel details
            hotel_dict = {
                'id': hotel.id,
                'property_name': hotel.property_name,
                'city': hotel.city,
                'country': hotel.country,
                'check_in': hotel.check_in_date.isoformat() if hotel.check_in_date else None,
                'check_out': hotel.check_out_date.isoformat() if hotel.check_out_date else None,
                'nights': nights,
                'cost': hotel.cost or 0,
                'cost_per_night': round((hotel.cost or 0) / nights, 2) if nights > 0 else 0,
                'confirmation': hotel.confirmation_number,
                'address': hotel.address
            }
            hotel_details.append(hotel_dict)
            
            # Aggregate statistics
            if hotel.city:
                city_stats[hotel.city]['count'] += 1
                city_stats[hotel.city]['nights'] += nights
                city_stats[hotel.city]['properties'].add(hotel.property_name)
            
            if hotel.property_name:
                property_stats[hotel.property_name] += 1
            
            # Monthly distribution
            if hotel.check_in_date:
                month_key = hotel.check_in_date.strftime('%Y-%m')
                monthly_nights[month_key] += nights
            
            total_nights += nights
            total_cost += hotel.cost or 0
        
        # Convert sets to counts for JSON
        for city in city_stats:
            city_stats[city]['unique_properties'] = len(city_stats[city]['properties'])
            del city_stats[city]['properties']
        
        # Top cities by nights
        top_cities = sorted(
            [(city, stats['nights']) for city, stats in city_stats.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Favorite properties (stayed more than once)
        favorite_properties = [(prop, count) for prop, count in property_stats.items() if count > 1]
        favorite_properties.sort(key=lambda x: x[1], reverse=True)
        
        return {
            'summary': {
                'total_stays': len(hotels),
                'total_nights': total_nights,
                'total_cost': round(total_cost, 2),
                'average_cost_per_night': round(total_cost / total_nights, 2) if total_nights > 0 else 0,
                'unique_cities': len(city_stats),
                'unique_properties': len(property_stats)
            },
            'city_breakdown': dict(city_stats),
            'top_cities': [{'city': city, 'nights': nights} for city, nights in top_cities],
            'favorite_properties': [{'property': prop, 'stays': count} for prop, count in favorite_properties],
            'monthly_distribution': dict(monthly_nights),
            'recent_stays': hotel_details[:20],
            'all_stays': hotel_details
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/statistics/costs")
async def get_cost_statistics_detail(
    year: Optional[int] = Query(None, description="Filter by year")
) -> Dict:
    """Get detailed cost breakdown statistics"""
    db = SessionLocal()
    try:
        # Initialize queries
        transport_query = db.query(TransportSegment).filter(TransportSegment.status != 'cancelled')
        accommodation_query = db.query(Accommodation).filter(Accommodation.status != 'cancelled')
        tour_query = db.query(TourActivity).filter(TourActivity.status != 'cancelled')
        cruise_query = db.query(Cruise).filter(Cruise.status != 'cancelled')
        
        if year:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
            
            transport_query = transport_query.filter(
                TransportSegment.departure_datetime >= start_date,
                TransportSegment.departure_datetime <= end_date
            )
            accommodation_query = accommodation_query.filter(
                Accommodation.check_in_date >= start_date.date(),
                Accommodation.check_in_date <= end_date.date()
            )
            tour_query = tour_query.filter(
                TourActivity.start_datetime >= start_date,
                TourActivity.start_datetime <= end_date
            )
            cruise_query = cruise_query.filter(
                Cruise.departure_datetime >= start_date,
                Cruise.departure_datetime <= end_date
            )
        
        # Get all bookings
        transports = transport_query.all()
        accommodations = accommodation_query.all()
        tours = tour_query.all()
        cruises = cruise_query.all()
        
        # Category breakdown
        category_costs = {
            'flights': sum(t.cost or 0 for t in transports if t.segment_type == 'flight'),
            'trains': sum(t.cost or 0 for t in transports if t.segment_type == 'train'),
            'other_transport': sum(t.cost or 0 for t in transports if t.segment_type not in ['flight', 'train']),
            'hotels': sum(a.cost or 0 for a in accommodations),
            'tours': sum(t.cost or 0 for t in tours),
            'cruises': sum(c.cost or 0 for c in cruises)
        }
        
        # Monthly spending
        monthly_spending = defaultdict(lambda: defaultdict(float))
        
        for transport in transports:
            if transport.departure_datetime and transport.cost:
                month = transport.departure_datetime.strftime('%Y-%m')
                monthly_spending[month]['transport'] += transport.cost
        
        for accommodation in accommodations:
            if accommodation.check_in_date and accommodation.cost:
                month = accommodation.check_in_date.strftime('%Y-%m')
                monthly_spending[month]['accommodation'] += accommodation.cost
        
        for tour in tours:
            if tour.start_datetime and tour.cost:
                month = tour.start_datetime.strftime('%Y-%m')
                monthly_spending[month]['tours'] += tour.cost
        
        # Most expensive items
        all_items = []
        
        for t in transports:
            if t.cost:
                all_items.append({
                    'type': 'Transport',
                    'description': f"{t.segment_type}: {t.departure_location} → {t.arrival_location}",
                    'date': t.departure_datetime.isoformat() if t.departure_datetime else None,
                    'cost': t.cost
                })
        
        for a in accommodations:
            if a.cost:
                all_items.append({
                    'type': 'Hotel',
                    'description': f"{a.property_name} in {a.city}",
                    'date': a.check_in_date.isoformat() if a.check_in_date else None,
                    'cost': a.cost
                })
        
        for tour in tours:
            if tour.cost:
                all_items.append({
                    'type': 'Tour',
                    'description': tour.activity_name,
                    'date': tour.start_datetime.isoformat() if tour.start_datetime else None,
                    'cost': tour.cost
                })
        
        # Sort by cost
        most_expensive = sorted(all_items, key=lambda x: x['cost'], reverse=True)[:20]
        
        # Cost by destination (from trips)
        trips = db.query(Trip).all()
        destination_costs = defaultdict(float)
        for trip in trips:
            if trip.destination and trip.total_cost:
                if not year or (trip.start_date and trip.start_date.year == year):
                    destination_costs[trip.destination] += trip.total_cost
        
        top_expensive_destinations = sorted(
            destination_costs.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        total_cost = sum(category_costs.values())
        
        return {
            'summary': {
                'total_cost': round(total_cost, 2),
                'average_per_trip': round(total_cost / len(trips), 2) if trips else 0,
                'most_expensive_category': max(category_costs.items(), key=lambda x: x[1])[0] if category_costs else None
            },
            'category_breakdown': category_costs,
            'monthly_spending': {k: dict(v) for k, v in monthly_spending.items()},
            'most_expensive_items': most_expensive,
            'top_expensive_destinations': [
                {'destination': dest, 'total_cost': round(cost, 2)} 
                for dest, cost in top_expensive_destinations
            ],
            'cost_distribution': {
                'under_100': len([i for i in all_items if i['cost'] < 100]),
                '100_500': len([i for i in all_items if 100 <= i['cost'] < 500]),
                '500_1000': len([i for i in all_items if 500 <= i['cost'] < 1000]),
                '1000_5000': len([i for i in all_items if 1000 <= i['cost'] < 5000]),
                'over_5000': len([i for i in all_items if i['cost'] >= 5000])
            }
        }
        
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