"""
Unit tests for Trip model JSON parsing and validation
"""
import pytest
from datetime import datetime
from backend.models.trip import Trip, TransportSegment, Accommodation


class TestTripJSONParsing:
    """Test Trip JSON parsing and validation"""
    
    def test_valid_trip_json(self):
        """Test parsing valid trip JSON"""
        trip_data = {
            "name": "Paris Business Trip",
            "destination": "Paris",
            "start_date": "2024-03-15",
            "end_date": "2024-03-18",
            "cities_visited": ["Paris"],
            "transport_segments": [
                {
                    "segment_type": "flight",
                    "departure_location": "Zurich",
                    "arrival_location": "Paris",
                    "departure_datetime": "2024-03-15T10:00:00",
                    "arrival_datetime": "2024-03-15T11:30:00",
                    "carrier_name": "Swiss Air",
                    "segment_number": "LX638",
                    "distance_km": 490,
                    "distance_type": "actual",
                    "cost": 250.0,
                    "confirmation_number": "ABC123"
                }
            ],
            "accommodations": [
                {
                    "property_name": "Hotel Le Marais",
                    "check_in_date": "2024-03-15",
                    "check_out_date": "2024-03-18",
                    "city": "Paris",
                    "cost": 450.0,
                    "confirmation_number": "HTL456"
                }
            ]
        }
        
        trip = Trip.from_json(trip_data)
        
        assert trip.name == "Paris Business Trip"
        assert trip.destination == "Paris"
        assert trip.start_date.date() == datetime(2024, 3, 15).date()
        assert trip.end_date.date() == datetime(2024, 3, 18).date()
        assert len(trip.transport_segments) == 1
        assert len(trip.accommodations) == 1
        assert trip.transport_segments[0].segment_type == "flight"
        assert trip.accommodations[0].property_name == "Hotel Le Marais"
    
    def test_missing_required_fields(self):
        """Test validation fails when required fields are missing"""
        # Missing name
        with pytest.raises(ValueError, match="Missing required fields: \\['name'\\]"):
            Trip.from_json({
                "start_date": "2024-03-15",
                "end_date": "2024-03-18"
            })
        
        # Missing dates
        with pytest.raises(ValueError, match="Missing required fields"):
            Trip.from_json({
                "name": "Test Trip"
            })
    
    def test_no_bookings(self):
        """Test validation fails when trip has no bookings"""
        with pytest.raises(ValueError, match="Trip must have at least one booking"):
            Trip.from_json({
                "name": "Empty Trip",
                "start_date": "2024-03-15",
                "end_date": "2024-03-18"
            })
    
    def test_invalid_date_order(self):
        """Test validation fails when end date is before start date"""
        with pytest.raises(ValueError, match="Trip end_date must be after start_date"):
            Trip.from_json({
                "name": "Invalid Trip",
                "start_date": "2024-03-18",
                "end_date": "2024-03-15",
                "transport_segments": [{
                    "segment_type": "flight",
                    "departure_location": "A",
                    "arrival_location": "B",
                    "departure_datetime": "2024-03-18T10:00:00",
                    "arrival_datetime": "2024-03-18T12:00:00"
                }]
            })
    
    def test_invalid_transport_segment(self):
        """Test validation fails for invalid transport segments"""
        # Missing required fields
        with pytest.raises(ValueError, match="Transport segment 0 missing required fields"):
            Trip.from_json({
                "name": "Test Trip",
                "start_date": "2024-03-15",
                "end_date": "2024-03-18",
                "transport_segments": [{
                    "segment_type": "flight"
                    # Missing locations and times
                }]
            })
        
        # Invalid arrival time (before departure)
        with pytest.raises(ValueError, match="Arrival datetime must be after departure datetime"):
            Trip.from_json({
                "name": "Test Trip",
                "start_date": "2024-03-15",
                "end_date": "2024-03-18",
                "transport_segments": [{
                    "segment_type": "flight",
                    "departure_location": "A",
                    "arrival_location": "B",
                    "departure_datetime": "2024-03-15T12:00:00",
                    "arrival_datetime": "2024-03-15T10:00:00"  # Before departure
                }]
            })
    
    def test_invalid_accommodation(self):
        """Test validation fails for invalid accommodations"""
        # Missing required fields
        with pytest.raises(ValueError, match="Accommodation 0 missing required fields"):
            Trip.from_json({
                "name": "Test Trip",
                "start_date": "2024-03-15",
                "end_date": "2024-03-18",
                "accommodations": [{
                    "property_name": "Hotel"
                    # Missing dates
                }]
            })
        
        # Invalid checkout date (before checkin)
        with pytest.raises(ValueError, match="Check-out date must be after check-in date"):
            Trip.from_json({
                "name": "Test Trip",
                "start_date": "2024-03-15",
                "end_date": "2024-03-18",
                "accommodations": [{
                    "property_name": "Hotel",
                    "check_in_date": "2024-03-18",
                    "check_out_date": "2024-03-15"  # Before check-in
                }]
            })
    
    def test_segment_type_normalization(self):
        """Test that segment types are normalized to lowercase"""
        trip_data = {
            "name": "Test Trip",
            "start_date": "2024-03-15",
            "end_date": "2024-03-18",
            "transport_segments": [{
                "segment_type": "FLIGHT",  # Uppercase
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00"
            }]
        }
        
        trip = Trip.from_json(trip_data)
        assert trip.transport_segments[0].segment_type == "flight"
    
    def test_unknown_segment_type(self):
        """Test that unknown segment types are converted to 'other'"""
        trip_data = {
            "name": "Test Trip",
            "start_date": "2024-03-15",
            "end_date": "2024-03-18",
            "transport_segments": [{
                "segment_type": "spaceship",  # Unknown type
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00"
            }]
        }
        
        trip = Trip.from_json(trip_data)
        assert trip.transport_segments[0].segment_type == "other"
    
    def test_distance_type_validation(self):
        """Test distance_type validation"""
        # Valid distance type
        trip_data = {
            "name": "Test Trip",
            "start_date": "2024-03-15",
            "end_date": "2024-03-18",
            "transport_segments": [{
                "segment_type": "flight",
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00",
                "distance_km": 500,
                "distance_type": "actual"
            }]
        }
        
        trip = Trip.from_json(trip_data)
        assert trip.transport_segments[0].distance_type == "actual"
        
        # Invalid distance type
        trip_data["transport_segments"][0]["distance_type"] = "estimated"
        with pytest.raises(ValueError, match='distance_type must be either "actual" or "straight"'):
            Trip.from_json(trip_data)
    
    def test_status_validation(self):
        """Test status field validation"""
        # Valid status
        trip_data = {
            "name": "Test Trip",
            "start_date": "2024-03-15",
            "end_date": "2024-03-18",
            "transport_segments": [{
                "segment_type": "flight",
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00",
                "status": "CANCELLED"  # Should be normalized
            }]
        }
        
        trip = Trip.from_json(trip_data)
        assert trip.transport_segments[0].status == "cancelled"
        
        # Invalid status
        trip_data["transport_segments"][0]["status"] = "unknown"
        with pytest.raises(ValueError, match="status must be one of"):
            Trip.from_json(trip_data)
    
    def test_date_parsing_formats(self):
        """Test various date format parsing"""
        # ISO format with time
        trip_data = {
            "name": "Test Trip",
            "start_date": "2024-03-15T00:00:00",
            "end_date": "2024-03-18T23:59:59",
            "transport_segments": [{
                "segment_type": "flight",
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00"
            }]
        }
        
        trip = Trip.from_json(trip_data)
        assert trip.start_date.date() == datetime(2024, 3, 15).date()
        assert trip.end_date.date() == datetime(2024, 3, 18).date()
    
    def test_total_cost_calculation(self):
        """Test automatic total cost calculation"""
        trip_data = {
            "name": "Test Trip",
            "start_date": "2024-03-15",
            "end_date": "2024-03-18",
            "transport_segments": [{
                "segment_type": "flight",
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00",
                "cost": 200.0
            }],
            "accommodations": [{
                "property_name": "Hotel",
                "check_in_date": "2024-03-15",
                "check_out_date": "2024-03-18",
                "cost": 300.0
            }]
        }
        
        trip = Trip.from_json(trip_data)
        assert trip.total_cost == 500.0
        
        # Test with provided total_cost
        trip_data["total_cost"] = 600.0
        trip2 = Trip.from_json(trip_data)
        assert trip2.total_cost == 600.0  # Uses provided value
    
    def test_complex_trip_with_all_segments(self):
        """Test parsing a complex trip with all segment types"""
        trip_data = {
            "name": "European Tour",
            "destination": "Europe",
            "start_date": "2024-06-01",
            "end_date": "2024-06-15",
            "cities_visited": ["Zurich", "Paris", "Rome", "Barcelona"],
            "transport_segments": [
                {
                    "segment_type": "flight",
                    "departure_location": "Zurich",
                    "arrival_location": "Paris",
                    "departure_datetime": "2024-06-01T08:00:00",
                    "arrival_datetime": "2024-06-01T09:30:00",
                    "cost": 150.0
                },
                {
                    "segment_type": "train",
                    "departure_location": "Paris",
                    "arrival_location": "Rome",
                    "departure_datetime": "2024-06-05T10:00:00",
                    "arrival_datetime": "2024-06-05T18:00:00",
                    "cost": 200.0
                }
            ],
            "accommodations": [
                {
                    "property_name": "Paris Hotel",
                    "check_in_date": "2024-06-01",
                    "check_out_date": "2024-06-05",
                    "city": "Paris",
                    "cost": 400.0
                },
                {
                    "property_name": "Rome B&B",
                    "check_in_date": "2024-06-05",
                    "check_out_date": "2024-06-10",
                    "city": "Rome",
                    "cost": 300.0
                }
            ],
            "tour_activities": [
                {
                    "activity_name": "Louvre Museum Tour",
                    "start_datetime": "2024-06-02T09:00:00",
                    "end_datetime": "2024-06-02T12:00:00",
                    "city": "Paris",
                    "cost": 50.0
                }
            ],
            "cruises": [
                {
                    "cruise_line": "Mediterranean Cruises",
                    "departure_datetime": "2024-06-10T18:00:00",
                    "arrival_datetime": "2024-06-12T08:00:00",
                    "itinerary": ["Rome", "Naples", "Barcelona"],
                    "cost": 500.0
                }
            ]
        }
        
        trip = Trip.from_json(trip_data)
        
        assert trip.name == "European Tour"
        assert len(trip.transport_segments) == 2
        assert len(trip.accommodations) == 2
        assert len(trip.tour_activities) == 1
        assert len(trip.cruises) == 1
        assert trip.total_cost == 1600.0  # Sum of all costs
        assert len(trip.cities_visited) == 4


class TestTripJSONStringParsing:
    """Test parsing Trip from JSON strings"""
    
    def test_parse_json_string(self):
        """Test parsing from JSON string"""
        json_str = """{
            "name": "Test Trip",
            "start_date": "2024-03-15",
            "end_date": "2024-03-18",
            "transport_segments": [{
                "segment_type": "flight",
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00"
            }]
        }"""
        
        trip = Trip.from_json_string(json_str)
        assert trip.name == "Test Trip"
    
    def test_invalid_json_string(self):
        """Test error handling for invalid JSON"""
        with pytest.raises(ValueError, match="Invalid JSON"):
            Trip.from_json_string("not a json")
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            Trip.from_json_string("{incomplete json")
    
    def test_json_array_rejected(self):
        """Test that JSON arrays are rejected"""
        with pytest.raises(ValueError, match="JSON must be an object"):
            Trip.from_json_string("[]")
        
        with pytest.raises(ValueError, match="JSON must be an object"):
            Trip.from_json_string('"string"')