"""
Unit tests for BookingInfo model JSON parsing and validation
"""
import pytest
from datetime import datetime
from backend.models.booking import (
    BookingInfo, BookingType, NonBookingType, BookingStatus,
    CostInfo, BookingDates, AdditionalInfo
)


class TestBookingInfoJSONParsing:
    """Test BookingInfo JSON parsing and validation"""
    
    def test_valid_flight_booking(self):
        """Test parsing valid flight booking JSON"""
        booking_data = {
            "booking_type": "flight",
            "status": "confirmed",
            "confirmation_numbers": ["ABC123", "XYZ789"],
            "transport_segments": [
                {
                    "segment_type": "flight",
                    "departure_location": "Zurich",
                    "arrival_location": "London",
                    "departure_datetime": "2024-03-15T10:00:00",
                    "arrival_datetime": "2024-03-15T11:30:00",
                    "carrier_name": "Swiss Air",
                    "flight_number": "LX456",
                    "cost": 250.0
                }
            ],
            "cost_info": {
                "total_cost": 250.0,
                "currency": "CHF",
                "cost_breakdown": {
                    "base_fare": 200.0,
                    "taxes": 50.0
                }
            },
            "dates": {
                "booking_date": "2024-02-15T14:30:00",
                "travel_start_date": "2024-03-15T10:00:00",
                "travel_end_date": "2024-03-15T11:30:00"
            },
            "additional_info": {
                "passenger_names": ["John Doe", "Jane Doe"],
                "special_requests": "Vegetarian meal"
            }
        }
        
        booking = BookingInfo.from_dict(booking_data)
        
        assert booking.booking_type == BookingType.FLIGHT
        assert booking.status == BookingStatus.CONFIRMED
        assert len(booking.confirmation_numbers) == 2
        assert "ABC123" in booking.confirmation_numbers
        assert len(booking.transport_segments) == 1
        assert booking.cost_info.total_cost == 250.0
        assert booking.cost_info.currency == "CHF"
        assert len(booking.additional_info.passenger_names) == 2
    
    def test_valid_hotel_booking(self):
        """Test parsing valid hotel booking JSON"""
        booking_data = {
            "booking_type": "hotel",
            "status": "confirmed",
            "confirmation_numbers": ["HTL456"],
            "accommodations": [
                {
                    "property_name": "Grand Hotel London",
                    "check_in_date": "2024-03-15",
                    "check_out_date": "2024-03-18",
                    "city": "London",
                    "room_type": "Double Room",
                    "cost": 450.0,
                    "confirmation_number": "HTL456"
                }
            ]
        }
        
        booking = BookingInfo.from_dict(booking_data)
        
        assert booking.booking_type == BookingType.HOTEL
        assert booking.is_booking() is True
        assert len(booking.accommodations) == 1
        assert booking.accommodations[0]["property_name"] == "Grand Hotel London"
    
    def test_non_booking_email(self):
        """Test parsing non-booking email"""
        booking_data = {
            "non_booking_type": "reminder",
            "reason": "Check-in reminder for upcoming flight"
        }
        
        booking = BookingInfo.from_dict(booking_data)
        
        assert booking.booking_type is None
        assert booking.non_booking_type == NonBookingType.REMINDER
        assert booking.is_booking() is False
        assert booking.reason == "Check-in reminder for upcoming flight"
    
    def test_booking_type_enum_conversion(self):
        """Test booking type enum conversion"""
        # Valid booking type
        booking_data = {"booking_type": "flight"}
        booking = BookingInfo.from_dict(booking_data)
        assert booking.booking_type == BookingType.FLIGHT
        
        # Invalid booking type
        booking_data = {"booking_type": "spaceship"}
        booking = BookingInfo.from_dict(booking_data)
        assert booking.booking_type is None
    
    def test_status_enum_conversion(self):
        """Test status enum conversion"""
        # Valid status
        booking_data = {
            "booking_type": "flight",
            "status": "cancelled",
            "transport_segments": []
        }
        booking = BookingInfo.from_dict(booking_data)
        assert booking.status == BookingStatus.CANCELLED
        
        # Invalid status - defaults to confirmed
        booking_data["status"] = "unknown"
        booking = BookingInfo.from_dict(booking_data)
        assert booking.status == BookingStatus.CONFIRMED
    
    def test_confirmation_number_list_conversion(self):
        """Test confirmation number list conversion"""
        # String converted to list
        booking_data = {
            "booking_type": "flight",
            "confirmation_numbers": "ABC123"
        }
        booking = BookingInfo.from_dict(booking_data)
        assert booking.confirmation_numbers == ["ABC123"]
        
        # Empty becomes empty list
        booking_data["confirmation_numbers"] = None
        booking = BookingInfo.from_dict(booking_data)
        assert booking.confirmation_numbers == []
    
    def test_is_complete_validation(self):
        """Test is_complete validation"""
        # Complete flight booking
        complete_flight = BookingInfo.from_dict({
            "booking_type": "flight",
            "transport_segments": [{
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00"
            }]
        })
        assert complete_flight.is_complete() is True
        
        # Incomplete flight - missing arrival time
        incomplete_flight = BookingInfo.from_dict({
            "booking_type": "flight",
            "transport_segments": [{
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00"
            }]
        })
        assert incomplete_flight.is_complete() is False
        
        # Complete hotel booking
        complete_hotel = BookingInfo.from_dict({
            "booking_type": "hotel",
            "accommodations": [{
                "property_name": "Hotel",
                "check_in_date": "2024-03-15",
                "check_out_date": "2024-03-18"
            }]
        })
        assert complete_hotel.is_complete() is True
        
        # Incomplete hotel - missing checkout date
        incomplete_hotel = BookingInfo.from_dict({
            "booking_type": "hotel",
            "accommodations": [{
                "property_name": "Hotel",
                "check_in_date": "2024-03-15"
            }]
        })
        assert incomplete_hotel.is_complete() is False
        
        # No segments
        no_segments = BookingInfo.from_dict({
            "booking_type": "flight"
        })
        assert no_segments.is_complete() is False
    
    def test_zurich_local_trip_detection(self):
        """Test Zurich local trip detection"""
        # Local Zurich trip
        zurich_trip = BookingInfo.from_dict({
            "booking_type": "train",
            "transport_segments": [{
                "departure_location": "Zurich HB",
                "arrival_location": "Winterthur",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T10:30:00"
            }]
        })
        assert zurich_trip.is_zurich_local_trip() is True
        
        # Non-local trip
        international_trip = BookingInfo.from_dict({
            "booking_type": "flight",
            "transport_segments": [{
                "departure_location": "Zurich Airport",
                "arrival_location": "London Heathrow",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T11:30:00"
            }]
        })
        assert international_trip.is_zurich_local_trip() is False
        
        # All activities in Zurich
        zurich_activities = BookingInfo.from_dict({
            "booking_type": "tour",
            "activities": [
                {"activity_name": "Tour 1", "city": "Zurich", "start_datetime": "2024-03-15T10:00:00"},
                {"activity_name": "Tour 2", "location": "Winterthur", "start_datetime": "2024-03-15T14:00:00"}
            ]
        })
        assert zurich_activities.is_zurich_local_trip() is True
    
    def test_test_booking_detection(self):
        """Test detection of test bookings"""
        # Test confirmation number
        test_booking = BookingInfo.from_dict({
            "booking_type": "flight",
            "confirmation_numbers": ["TEST123"],
            "transport_segments": []
        })
        assert test_booking._is_test_booking() is True
        
        # Test passenger name
        test_passenger = BookingInfo.from_dict({
            "booking_type": "hotel",
            "accommodations": [],
            "additional_info": {
                "passenger_names": ["Test User", "Demo Customer"]
            }
        })
        assert test_passenger._is_test_booking() is True
        
        # Normal booking
        normal_booking = BookingInfo.from_dict({
            "booking_type": "flight",
            "confirmation_numbers": ["ABC123"],
            "transport_segments": [],
            "additional_info": {
                "passenger_names": ["John Doe"]
            }
        })
        assert normal_booking._is_test_booking() is False
    
    def test_validate_for_trip_detection(self):
        """Test complete validation for trip detection"""
        # Valid booking
        valid_booking = BookingInfo.from_dict({
            "booking_type": "flight",
            "transport_segments": [{
                "departure_location": "Zurich",
                "arrival_location": "Paris",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T11:30:00"
            }]
        })
        is_valid, reason = valid_booking.validate_for_trip_detection()
        assert is_valid is True
        assert reason is None
        
        # Non-booking
        non_booking = BookingInfo.from_dict({
            "non_booking_type": "reminder"
        })
        is_valid, reason = non_booking.validate_for_trip_detection()
        assert is_valid is False
        assert "Non-booking email" in reason
        
        # Incomplete booking
        incomplete = BookingInfo.from_dict({
            "booking_type": "flight"
        })
        is_valid, reason = incomplete.validate_for_trip_detection()
        assert is_valid is False
        assert "Incomplete booking" in reason
        
        # Zurich local trip
        local_trip = BookingInfo.from_dict({
            "booking_type": "train",
            "transport_segments": [{
                "departure_location": "Zurich HB",
                "arrival_location": "Winterthur",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T10:30:00"
            }]
        })
        is_valid, reason = local_trip.validate_for_trip_detection()
        assert is_valid is False
        assert "Local Zurich trip" in reason
        
        # Test booking
        test_booking = BookingInfo.from_dict({
            "booking_type": "flight",
            "confirmation_numbers": ["DEMO123"],
            "transport_segments": [{
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00"
            }]
        })
        is_valid, reason = test_booking.validate_for_trip_detection()
        assert is_valid is False
        assert "Test booking" in reason
    
    def test_get_all_confirmation_numbers(self):
        """Test getting all confirmation numbers from all segments"""
        booking = BookingInfo.from_dict({
            "booking_type": "flight",
            "confirmation_numbers": ["MAIN123"],
            "transport_segments": [{
                "confirmation_number": "FLT456"
            }],
            "accommodations": [{
                "confirmation_number": "HTL789"
            }],
            "activities": [{
                "confirmation_number": "ACT012"
            }],
            "cruises": [{
                "confirmation_number": "CRZ345"
            }]
        })
        
        all_numbers = booking.get_all_confirmation_numbers()
        assert len(all_numbers) == 5
        assert "MAIN123" in all_numbers
        assert "FLT456" in all_numbers
        assert "HTL789" in all_numbers
        assert "ACT012" in all_numbers
        assert "CRZ345" in all_numbers
    
    def test_get_travel_date_range(self):
        """Test getting overall travel date range"""
        booking = BookingInfo.from_dict({
            "booking_type": "flight",
            "transport_segments": [{
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00"
            }],
            "accommodations": [{
                "check_in_date": "2024-03-15T14:00:00",
                "check_out_date": "2024-03-18T11:00:00"
            }],
            "activities": [{
                "start_datetime": "2024-03-16T09:00:00",
                "end_datetime": "2024-03-16T17:00:00"
            }]
        })
        
        start_date, end_date = booking.get_travel_date_range()
        assert start_date == datetime(2024, 3, 15, 10, 0, 0)
        assert end_date == datetime(2024, 3, 18, 11, 0, 0)
        
        # No dates
        empty_booking = BookingInfo.from_dict({
            "booking_type": "flight"
        })
        start_date, end_date = empty_booking.get_travel_date_range()
        assert start_date is None
        assert end_date is None
    
    def test_get_total_cost(self):
        """Test total cost calculation"""
        booking = BookingInfo.from_dict({
            "booking_type": "flight",
            "transport_segments": [{
                "cost": 200.0
            }, {
                "cost": 150.0
            }],
            "accommodations": [{
                "cost": 300.0
            }],
            "activities": [{
                "cost": 50.0
            }],
            "cruises": [{
                "cost": 500.0
            }]
        })
        
        assert booking.get_total_cost() == 1200.0
        
        # With cost_info override
        booking_with_cost_info = BookingInfo.from_dict({
            "booking_type": "flight",
            "transport_segments": [{"cost": 200.0}],
            "cost_info": {
                "total_cost": 250.0  # Higher than segment cost
            }
        })
        
        assert booking_with_cost_info.get_total_cost() == 250.0
    
    def test_from_json_string(self):
        """Test creating BookingInfo from JSON string"""
        json_str = """{
            "booking_type": "flight",
            "status": "confirmed",
            "confirmation_numbers": ["ABC123"],
            "transport_segments": [{
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00"
            }]
        }"""
        
        booking = BookingInfo.from_json(json_str)
        assert booking.booking_type == BookingType.FLIGHT
        assert booking.confirmation_numbers == ["ABC123"]
        
        # Invalid JSON
        with pytest.raises(Exception):
            BookingInfo.from_json("not valid json")
    
    def test_to_json_roundtrip(self):
        """Test JSON serialization roundtrip"""
        original_data = {
            "booking_type": "hotel",
            "status": "confirmed",
            "confirmation_numbers": ["HTL123"],
            "accommodations": [{
                "property_name": "Test Hotel",
                "check_in_date": "2024-03-15",
                "check_out_date": "2024-03-18",
                "cost": 300.0
            }],
            "cost_info": {
                "total_cost": 300.0,
                "currency": "USD"
            },
            "dates": {
                "booking_date": "2024-02-15T10:00:00"
            }
        }
        
        booking = BookingInfo.from_dict(original_data)
        json_str = booking.to_json()
        
        # Parse back
        restored = BookingInfo.from_json(json_str)
        
        assert restored.booking_type == booking.booking_type
        assert restored.confirmation_numbers == booking.confirmation_numbers
        assert len(restored.accommodations) == len(booking.accommodations)
        assert restored.cost_info.total_cost == booking.cost_info.total_cost
    
    def test_to_email_data_dict(self):
        """Test conversion to email data dict for TripDetector"""
        booking = BookingInfo.from_dict({
            "booking_type": "flight",
            "transport_segments": [{
                "departure_location": "A",
                "arrival_location": "B",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00"
            }]
        })
        
        # Mock email object
        class MockEmail:
            email_id = "test123"
            subject = "Flight Confirmation"
            sender = "airline@example.com"
            timestamp = datetime(2024, 2, 15, 10, 0, 0)
            classification = "flight"
        
        email_data = booking.to_email_data_dict(MockEmail())
        
        assert email_data["email_id"] == "test123"
        assert email_data["subject"] == "Flight Confirmation"
        assert email_data["sender"] == "airline@example.com"
        assert email_data["classification"] == "flight"
        assert "extracted_booking_info" in email_data
        assert email_data["extracted_booking_info"]["booking_type"] == "flight"


class TestBookingInfoComplexScenarios:
    """Test complex booking scenarios"""
    
    def test_multi_segment_booking(self):
        """Test booking with multiple segments of different types"""
        booking_data = {
            "booking_type": "flight",
            "status": "confirmed",
            "confirmation_numbers": ["MULTI123"],
            "transport_segments": [
                {
                    "segment_type": "flight",
                    "departure_location": "Zurich",
                    "arrival_location": "London",
                    "departure_datetime": "2024-03-15T08:00:00",
                    "arrival_datetime": "2024-03-15T09:30:00",
                    "cost": 200.0
                },
                {
                    "segment_type": "train",
                    "departure_location": "London",
                    "arrival_location": "Edinburgh",
                    "departure_datetime": "2024-03-15T11:00:00",
                    "arrival_datetime": "2024-03-15T16:00:00",
                    "cost": 150.0
                }
            ],
            "accommodations": [
                {
                    "property_name": "Edinburgh Hotel",
                    "check_in_date": "2024-03-15",
                    "check_out_date": "2024-03-18",
                    "cost": 450.0
                }
            ],
            "activities": [
                {
                    "activity_name": "Edinburgh Castle Tour",
                    "start_datetime": "2024-03-16T10:00:00",
                    "end_datetime": "2024-03-16T12:00:00",
                    "cost": 30.0
                }
            ]
        }
        
        booking = BookingInfo.from_dict(booking_data)
        
        assert booking.is_complete() is True
        assert booking.get_total_cost() == 830.0
        start_date, end_date = booking.get_travel_date_range()
        # Check-in/out dates are parsed as date-only strings, so they become midnight
        assert start_date == datetime(2024, 3, 15, 0, 0, 0)  # Check-in date at midnight
        assert end_date == datetime(2024, 3, 18, 0, 0, 0)  # Check-out date at midnight
    
    def test_cancellation_booking(self):
        """Test cancellation booking handling"""
        booking_data = {
            "booking_type": "flight",
            "status": "cancelled",
            "original_booking_reference": "ORIG123",
            "confirmation_numbers": ["CANC456"],
            "transport_segments": [{
                "departure_location": "Zurich",
                "arrival_location": "Rome",
                "departure_datetime": "2024-03-15T10:00:00",
                "arrival_datetime": "2024-03-15T12:00:00",
                "status": "cancelled"
            }]
        }
        
        booking = BookingInfo.from_dict(booking_data)
        
        assert booking.status == BookingStatus.CANCELLED
        assert booking.original_booking_reference == "ORIG123"
        assert booking.is_complete() is True  # Cancelled bookings can still be complete
    
    def test_modification_booking(self):
        """Test modification booking handling"""
        booking_data = {
            "booking_type": "hotel",
            "status": "modified",
            "original_booking_reference": "HTL789",
            "confirmation_numbers": ["HTL789-MOD"],
            "accommodations": [{
                "property_name": "Grand Hotel",
                "check_in_date": "2024-03-16",  # Changed date
                "check_out_date": "2024-03-19",
                "notes": "Check-in date changed from March 15"
            }]
        }
        
        booking = BookingInfo.from_dict(booking_data)
        
        assert booking.status == BookingStatus.MODIFIED
        assert booking.original_booking_reference == "HTL789"


class TestBookingInfoEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_booking(self):
        """Test handling of empty booking"""
        booking = BookingInfo()
        
        assert booking.booking_type is None
        assert booking.is_booking() is False
        assert booking.is_complete() is False
        assert booking.get_total_cost() == 0.0
        assert booking.get_all_confirmation_numbers() == []
    
    def test_partial_dates(self):
        """Test handling of partial date information"""
        booking = BookingInfo.from_dict({
            "booking_type": "cruise",
            "cruises": [{
                "cruise_line": "Test Cruise",
                "departure_datetime": "2024-03-15T18:00:00",
                "arrival_datetime": None,  # Missing arrival
                "cost": 1000.0
            }]
        })
        
        # Should still calculate date range with available dates
        start_date, end_date = booking.get_travel_date_range()
        assert start_date == datetime(2024, 3, 15, 18, 0, 0)
        assert end_date == datetime(2024, 3, 15, 18, 0, 0)  # Same as start when only one date
    
    def test_malformed_datetime_handling(self):
        """Test handling of malformed datetime strings"""
        with pytest.raises(Exception):
            BookingInfo.from_dict({
                "booking_type": "flight",
                "dates": {
                    "booking_date": "not-a-date"
                }
            })
    
    def test_very_long_confirmation_numbers(self):
        """Test handling of very long confirmation numbers"""
        long_conf_nums = ["A" * 100 for _ in range(10)]
        booking = BookingInfo.from_dict({
            "booking_type": "hotel",
            "confirmation_numbers": long_conf_nums,
            "accommodations": [{
                "property_name": "Hotel",
                "check_in_date": "2024-03-15",
                "check_out_date": "2024-03-18"
            }]
        })
        
        assert len(booking.confirmation_numbers) == 10
        assert all(len(num) == 100 for num in booking.confirmation_numbers)