"""
Trip Detector Integration Tests

Tests the TripDetector class with real AI providers to validate trip detection functionality.
"""
import pytest
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from lib.trip_detector import TripDetector
from lib.ai.ai_provider_factory import AIProviderFactory
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestTripDetector:
    """Integration tests for TripDetector using real AI providers"""
    
    @pytest.fixture
    def single_flight_booking_data(self):
        """Load single flight booking test data"""
        test_data_path = os.path.join(
            os.path.dirname(__file__), 
            'test_data', 
            'level_1_single_booking',
            'single_flight_booking.json'
        )
        with open(test_data_path, 'r') as f:
            return json.load(f)
    
    @pytest.fixture
    def expected_trip_output(self):
        """Load expected trip output"""
        expected_path = os.path.join(
            os.path.dirname(__file__),
            'test_data',
            'level_1_single_booking', 
            'expected_trip_output.json'
        )
        with open(expected_path, 'r') as f:
            return json.load(f)
    
    def validate_trip_structure(self, trip: Dict) -> None:
        """Validate that a trip has all required fields"""
        required_fields = [
            'name', 'destination', 'start_date', 'end_date',
            'cities_visited', 'total_cost', 'transport_segments',
            'accommodations', 'tour_activities', 'cruises'
        ]
        
        for field in required_fields:
            assert field in trip, f"Trip missing required field: {field}"
        
        # Validate transport segments
        for segment in trip.get('transport_segments', []):
            segment_required = [
                'segment_type', 'departure_location', 'arrival_location',
                'departure_datetime', 'arrival_datetime', 'carrier_name',
                'segment_number', 'distance_km', 'distance_type',
                'booking_platform', 'confirmation_number', 'status',
                'is_latest_version', 'related_email_ids'
            ]
            for field in segment_required:
                assert field in segment, f"Transport segment missing field: {field}"
    
    def compare_trips(self, actual: Dict, expected: Dict, allow_variations: bool = True) -> None:
        """Compare actual trip output with expected, allowing for AI variations"""
        # Basic structure comparison
        assert actual['start_date'] == expected['start_date']
        assert actual['end_date'] == expected['end_date']
        assert actual['destination'] == expected['destination']
        
        # Cities visited should match
        assert actual['cities_visited'] == expected['cities_visited']
        
        # Transport segments count should match
        assert len(actual['transport_segments']) == len(expected['transport_segments'])
        
        # Validate each transport segment
        for i, (actual_seg, expected_seg) in enumerate(zip(
            actual['transport_segments'], 
            expected['transport_segments']
        )):
            assert actual_seg['segment_type'] == expected_seg['segment_type']
            assert actual_seg['departure_location'] == expected_seg['departure_location']
            assert actual_seg['arrival_location'] == expected_seg['arrival_location']
            assert actual_seg['departure_datetime'] == expected_seg['departure_datetime']
            assert actual_seg['arrival_datetime'] == expected_seg['arrival_datetime']
            assert actual_seg['confirmation_number'] == expected_seg['confirmation_number']
            
            # Distance should be present and reasonable
            assert 'distance_km' in actual_seg
            assert actual_seg['distance_km'] > 0
            
            # Email IDs should be associated
            assert 'test_single_flight_001' in actual_seg['related_email_ids']
        
        # Cost validation (allow some variation)
        if allow_variations:
            # AI might calculate costs differently
            assert actual['total_cost'] > 0
        else:
            assert abs(actual['total_cost'] - expected['total_cost']) < 0.01
    
    @pytest.mark.parametrize("provider_name,model_tier", [
        ("gemini", "fast"),
        ("gemini", "powerful"),
        ("openai", "fast"), 
        ("openai", "powerful"),
        ("claude", "fast"),
        ("claude", "powerful")
    ])
    def test_all_model_combinations(self, single_flight_booking_data, expected_trip_output, provider_name, model_tier):
        """Test trip detection with all combinations of providers and model tiers"""
        logger.info(f"\n=== Testing {provider_name} + {model_tier} ===")
        
        # Create AI provider
        try:
            ai_provider = AIProviderFactory.create_provider(
                model_tier=model_tier,
                provider_name=provider_name
            )
            model_info = ai_provider.get_model_info()
            logger.info(f"Created AI provider: {model_info}")
        except Exception as e:
            pytest.skip(f"Could not create {provider_name} {model_tier} provider: {e}")
        
        # Create trip detector
        detector = TripDetector(ai_provider)
        
        # Detect trips
        emails = [single_flight_booking_data]
        existing_trips = []
        
        try:
            detected_trips = detector.detect_trips(emails, existing_trips)
        except Exception as e:
            pytest.fail(f"Trip detection failed with {provider_name} {model_tier}: {e}")
        
        # Validate results
        assert detected_trips is not None, "Trip detection returned None (critical error)"
        assert len(detected_trips) == 1, f"Expected 1 trip, got {len(detected_trips)}"
        
        trip = detected_trips[0]
        logger.info(f"Detected trip: {trip['name']}")
        
        # Validate structure
        self.validate_trip_structure(trip)
        
        # Compare with expected output
        expected_trips = expected_trip_output['trips']
        self.compare_trips(trip, expected_trips[0])
        
        # Store result for comparison
        self._store_result_for_comparison(provider_name, model_tier, trip)
        
        logger.info(f"✓ {provider_name} {model_tier} test passed")
    
    def _store_result_for_comparison(self, provider_name: str, model_tier: str, trip: Dict):
        """Store test results for later comparison"""
        if not hasattr(self, '_test_results'):
            self._test_results = {}
        
        key = f"{provider_name}_{model_tier}"
        self._test_results[key] = trip
    
    def test_compare_all_models(self, single_flight_booking_data):
        """Compare outputs from all model combinations"""
        logger.info("\n=== Comparing all model outputs ===")
        
        # Collect results from all combinations
        results = {}
        providers = ["gemini", "openai", "claude"]
        tiers = ["fast", "powerful"]
        
        for provider_name in providers:
            for model_tier in tiers:
                try:
                    ai_provider = AIProviderFactory.create_provider(
                        model_tier=model_tier,
                        provider_name=provider_name
                    )
                    detector = TripDetector(ai_provider)
                    trips = detector.detect_trips([single_flight_booking_data], [])
                    
                    if trips and len(trips) > 0:
                        key = f"{provider_name}_{model_tier}"
                        results[key] = trips[0]
                        logger.info(f"✓ Collected result from {key}")
                    
                except Exception as e:
                    logger.warning(f"Could not test {provider_name} {model_tier}: {e}")
                    continue
        
        if len(results) < 2:
            pytest.skip("Not enough models available for comparison")
        
        # Compare all results
        logger.info(f"\nCollected {len(results)} results for comparison:")
        
        # Check consistency across all models
        destinations = set()
        start_dates = set()
        end_dates = set()
        segment_counts = set()
        trip_names = {}
        total_costs = {}
        
        for key, trip in results.items():
            destinations.add(trip['destination'])
            start_dates.add(trip['start_date'])
            end_dates.add(trip['end_date'])
            segment_counts.add(len(trip['transport_segments']))
            trip_names[key] = trip['name']
            total_costs[key] = trip['total_cost']
        
        # All models should agree on core facts
        assert len(destinations) == 1, f"Models disagree on destination: {destinations}"
        assert len(start_dates) == 1, f"Models disagree on start date: {start_dates}"
        assert len(end_dates) == 1, f"Models disagree on end date: {end_dates}"
        assert len(segment_counts) == 1, f"Models disagree on segment count: {segment_counts}"
        
        # Log variations in trip names and costs
        logger.info("\nTrip names by model:")
        for key, name in sorted(trip_names.items()):
            logger.info(f"  {key}: {name}")
        
        logger.info("\nTotal costs by model:")
        for key, cost in sorted(total_costs.items()):
            logger.info(f"  {key}: {cost} CHF")
        
        # Calculate cost variation
        costs = list(total_costs.values())
        if costs:
            min_cost = min(costs)
            max_cost = max(costs)
            variation = ((max_cost - min_cost) / min_cost * 100) if min_cost > 0 else 0
            logger.info(f"\nCost variation: {variation:.1f}% (min: {min_cost}, max: {max_cost})")
        
        logger.info("\n✓ All models produced consistent core results")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])