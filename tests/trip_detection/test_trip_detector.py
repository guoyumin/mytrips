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
from pathlib import Path

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
    
    @property
    def test_log_path(self):
        """Get test log path"""
        path = Path(__file__).parent / "test_data" / "test_runs.jsonl"
        path.parent.mkdir(exist_ok=True)
        return path
    
    def log_test_run(self, provider_name: str, model_tier: str, input_text: str, 
                     output_text: str, input_tokens: int, output_tokens: int, 
                     total_cost: float, success: bool, error_msg: str = None):
        """Log detailed test run information"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider_name,
            "model_tier": model_tier,
            "input_char_count": len(input_text),
            "output_char_count": len(output_text),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": total_cost,
            "success": success,
            "error": error_msg,
            "input_preview": input_text[:200] + "..." if len(input_text) > 200 else input_text,
            "output_preview": output_text[:200] + "..." if len(output_text) > 200 else output_text
        }
        
        # Append to log file
        with open(self.test_log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
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
        
        # Create trip detector with modified detect_trips method to capture token usage
        detector = TripDetector(ai_provider)
        
        # We need to capture the AI response details, so let's call the internal methods
        emails = [single_flight_booking_data]
        existing_trips = []
        
        try:
            # Create prompt (this is what gets sent to the AI)
            prompt = detector._create_trip_detection_prompt(emails, existing_trips)
            prompt_length = len(prompt)
            
            logger.info(f"Prompt length: {prompt_length:,} characters")
            
            # Call AI provider and get full response
            ai_response = ai_provider.generate_content(prompt)
            
            # Extract all the details
            response_text = ai_response['content']
            input_tokens = ai_response['input_tokens']
            output_tokens = ai_response['output_tokens']
            total_tokens = ai_response['total_tokens']
            estimated_cost = ai_response['estimated_cost_usd']
            
            # Log the detailed information
            logger.info(f"\n=== Token Usage Details ===")
            logger.info(f"Input characters: {len(prompt):,}")
            logger.info(f"Output characters: {len(response_text):,}")
            logger.info(f"Input tokens: {input_tokens:,}")
            logger.info(f"Output tokens: {output_tokens:,}")
            logger.info(f"Total tokens: {total_tokens:,}")
            logger.info(f"Estimated cost: ${estimated_cost:.6f}")
            logger.info(f"========================\n")
            
            # Parse the response to get trips
            detected_trips = detector._parse_ai_response(response_text, emails)
            
            # Log the test run
            self.log_test_run(
                provider_name=provider_name,
                model_tier=model_tier,
                input_text=prompt,
                output_text=response_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_cost=estimated_cost,
                success=bool(detected_trips),
                error_msg=None
            )
            
        except Exception as e:
            # Log the failure
            self.log_test_run(
                provider_name=provider_name,
                model_tier=model_tier,
                input_text=prompt if 'prompt' in locals() else "",
                output_text="",
                input_tokens=0,
                output_tokens=0,
                total_cost=0.0,
                success=False,
                error_msg=str(e)
            )
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
    
    # Level 2 Tests - Multi Booking
    @pytest.mark.parametrize("provider_name,model_tier", [
        ("gemini", "fast"),
        ("openai", "fast"),
        ("claude", "fast")
    ])
    def test_level2_multi_booking_flight_hotel(self, provider_name, model_tier):
        """Test Level 2: Multiple bookings (flight + hotel) forming one trip"""
        logger.info(f"\n=== Testing Level 2 Flight+Hotel: {provider_name} + {model_tier} ===")
        
        # Load test data
        test_data_path = os.path.join(
            os.path.dirname(__file__), 
            'test_data', 
            'level_2_multi_booking',
            'multi_booking_flight_hotel.json'
        )
        with open(test_data_path, 'r') as f:
            test_data = json.load(f)
        
        # Create AI provider
        try:
            ai_provider = AIProviderFactory.create_provider(
                model_tier=model_tier,
                provider_name=provider_name
            )
        except Exception as e:
            pytest.skip(f"Could not create {provider_name} {model_tier} provider: {e}")
        
        # Run detection with detailed logging
        detector = TripDetector(ai_provider)
        emails = test_data['emails']
        
        try:
            prompt = detector._create_trip_detection_prompt(emails, [])
            ai_response = ai_provider.generate_content(prompt)
            
            # Log details
            logger.info(f"Input: {len(prompt):,} chars / {ai_response['input_tokens']:,} tokens")
            logger.info(f"Output: {len(ai_response['content']):,} chars / {ai_response['output_tokens']:,} tokens")
            logger.info(f"Cost: ${ai_response['estimated_cost_usd']:.6f}")
            
            detected_trips = detector._parse_ai_response(ai_response['content'], emails)
            
            self.log_test_run(
                provider_name=provider_name,
                model_tier=model_tier,
                input_text=prompt,
                output_text=ai_response['content'],
                input_tokens=ai_response['input_tokens'],
                output_tokens=ai_response['output_tokens'],
                total_cost=ai_response['estimated_cost_usd'],
                success=bool(detected_trips),
                error_msg=None
            )
            
        except Exception as e:
            pytest.fail(f"Trip detection failed: {e}")
        
        # Validate results
        assert len(detected_trips) == 1, f"Expected 1 trip, got {len(detected_trips)}"
        trip = detected_trips[0]
        assert trip['destination'] == 'Barcelona'
        assert len(trip['transport_segments']) == 3  # ZRH->CDG->BCN + BCN->ZRH
        assert len(trip['accommodations']) == 1
        assert trip['accommodations'][0]['property_name'] == 'Hotel Barcelona Center'
        
        logger.info(f"✓ Level 2 test passed for {provider_name} {model_tier}")
    
    # Level 3 Tests - Existing Trip Merging
    @pytest.mark.parametrize("provider_name,model_tier", [
        ("gemini", "fast")
    ])
    def test_level3_add_to_existing_trip(self, provider_name, model_tier):
        """Test Level 3: Adding activity to existing trip"""
        logger.info(f"\n=== Testing Level 3 Add Activity: {provider_name} + {model_tier} ===")
        
        # Load existing trip data
        existing_trip_path = os.path.join(
            os.path.dirname(__file__), 
            'test_data', 
            'level_3_existing_trips',
            'existing_paris_trip.json'
        )
        with open(existing_trip_path, 'r') as f:
            existing_data = json.load(f)
        
        # Load new booking data
        new_booking_path = os.path.join(
            os.path.dirname(__file__), 
            'test_data', 
            'level_3_existing_trips',
            'new_louvre_booking.json'
        )
        with open(new_booking_path, 'r') as f:
            new_data = json.load(f)
        
        # Create AI provider
        try:
            ai_provider = AIProviderFactory.create_provider(
                model_tier=model_tier,
                provider_name=provider_name
            )
        except Exception as e:
            pytest.skip(f"Could not create {provider_name} {model_tier} provider: {e}")
        
        # Run detection
        detector = TripDetector(ai_provider)
        emails = new_data['new_emails']
        existing_trips = existing_data['existing_trips']
        
        try:
            prompt = detector._create_trip_detection_prompt(emails, existing_trips)
            ai_response = ai_provider.generate_content(prompt)
            
            logger.info(f"Cost: ${ai_response['estimated_cost_usd']:.6f}")
            
            detected_trips = detector._parse_ai_response(ai_response['content'], emails)
            
            self.log_test_run(
                provider_name=provider_name,
                model_tier=model_tier,
                input_text=prompt,
                output_text=ai_response['content'],
                input_tokens=ai_response['input_tokens'],
                output_tokens=ai_response['output_tokens'],
                total_cost=ai_response['estimated_cost_usd'],
                success=bool(detected_trips),
                error_msg=None
            )
            
        except Exception as e:
            pytest.fail(f"Trip detection failed: {e}")
        
        # Validate - should still have 1 trip with added activity
        assert len(detected_trips) == 1
        trip = detected_trips[0]
        assert trip['destination'] == 'Paris'
        assert len(trip['tour_activities']) >= 1
        assert any('Louvre' in activity.get('activity_name', '') 
                  for activity in trip['tour_activities'])
        
        logger.info(f"✓ Level 3 test passed")
    
    # Level 5 Tests - Edge Cases
    @pytest.mark.parametrize("provider_name,model_tier", [
        ("gemini", "fast")
    ])
    def test_level5_same_day_trips(self, provider_name, model_tier):
        """Test Level 5: Same day multiple trips"""
        logger.info(f"\n=== Testing Level 5 Same Day Trips: {provider_name} + {model_tier} ===")
        
        # Load test data
        test_data_path = os.path.join(
            os.path.dirname(__file__), 
            'test_data', 
            'level_5_edge_cases',
            'same_day_trips.json'
        )
        with open(test_data_path, 'r') as f:
            test_data = json.load(f)
        
        # Create AI provider
        try:
            ai_provider = AIProviderFactory.create_provider(
                model_tier=model_tier,
                provider_name=provider_name
            )
        except Exception as e:
            pytest.skip(f"Could not create {provider_name} {model_tier} provider: {e}")
        
        # Run detection
        detector = TripDetector(ai_provider)
        emails = test_data['emails']
        
        try:
            prompt = detector._create_trip_detection_prompt(emails, [])
            ai_response = ai_provider.generate_content(prompt)
            
            logger.info(f"Cost: ${ai_response['estimated_cost_usd']:.6f}")
            
            detected_trips = detector._parse_ai_response(ai_response['content'], emails)
            
            self.log_test_run(
                provider_name=provider_name,
                model_tier=model_tier,
                input_text=prompt,
                output_text=ai_response['content'],
                input_tokens=ai_response['input_tokens'],
                output_tokens=ai_response['output_tokens'],
                total_cost=ai_response['estimated_cost_usd'],
                success=bool(detected_trips),
                error_msg=None
            )
            
        except Exception as e:
            pytest.fail(f"Trip detection failed: {e}")
        
        # Should detect 2 separate trips
        assert len(detected_trips) == 2, f"Expected 2 trips, got {len(detected_trips)}"
        
        # Find Munich and Milan trips
        destinations = [trip['destination'] for trip in detected_trips]
        logger.info(f"Detected destinations: {destinations}")
        
        # One should be same-day Munich trip
        munich_trips = [t for t in detected_trips if 'Munich' in str(t.get('destination', ''))]
        assert len(munich_trips) == 1
        munich_trip = munich_trips[0]
        assert munich_trip['start_date'] == munich_trip['end_date']
        
        logger.info(f"✓ Level 5 test passed")
    
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
    
    def generate_test_summary(self):
        """Generate a summary report of all test runs"""
        if not self.test_log_path.exists():
            logger.warning("No test log file found")
            return
        
        # Read all test entries
        entries = []
        with open(self.test_log_path, 'r') as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except:
                    continue
        
        if not entries:
            logger.warning("No test entries found")
            return
        
        # Generate summary
        summary = {
            "total_runs": len(entries),
            "successful_runs": sum(1 for e in entries if e.get('success', False)),
            "failed_runs": sum(1 for e in entries if not e.get('success', False)),
            "total_cost": sum(e.get('cost_usd', 0) for e in entries),
            "total_tokens": sum(e.get('total_tokens', 0) for e in entries),
            "by_provider": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Group by provider and model
        for entry in entries:
            provider = entry.get('provider', 'unknown')
            model_tier = entry.get('model_tier', 'unknown')
            key = f"{provider}_{model_tier}"
            
            if key not in summary['by_provider']:
                summary['by_provider'][key] = {
                    'runs': 0,
                    'successful': 0,
                    'total_cost': 0,
                    'total_tokens': 0,
                    'avg_input_tokens': 0,
                    'avg_output_tokens': 0
                }
            
            stats = summary['by_provider'][key]
            stats['runs'] += 1
            if entry.get('success', False):
                stats['successful'] += 1
            stats['total_cost'] += entry.get('cost_usd', 0)
            stats['total_tokens'] += entry.get('total_tokens', 0)
        
        # Calculate averages
        for key, stats in summary['by_provider'].items():
            if stats['runs'] > 0:
                # Get all entries for this provider/model
                provider_entries = [e for e in entries 
                                  if f"{e.get('provider')}_{e.get('model_tier')}" == key]
                stats['avg_input_tokens'] = sum(e.get('input_tokens', 0) for e in provider_entries) / len(provider_entries)
                stats['avg_output_tokens'] = sum(e.get('output_tokens', 0) for e in provider_entries) / len(provider_entries)
                stats['avg_cost_per_run'] = stats['total_cost'] / stats['runs']
        
        # Save summary
        summary_path = self.test_log_path.parent / "test_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Print summary
        logger.info("\n=== Test Run Summary ===")
        logger.info(f"Total test runs: {summary['total_runs']}")
        logger.info(f"Successful: {summary['successful_runs']}")
        logger.info(f"Failed: {summary['failed_runs']}")
        logger.info(f"Total cost: ${summary['total_cost']:.4f}")
        logger.info(f"Total tokens: {summary['total_tokens']:,}")
        
        logger.info("\nBy Provider/Model:")
        for key, stats in sorted(summary['by_provider'].items()):
            logger.info(f"\n{key}:")
            logger.info(f"  Runs: {stats['runs']} (Success: {stats['successful']})")
            logger.info(f"  Total cost: ${stats['total_cost']:.4f}")
            logger.info(f"  Avg cost/run: ${stats.get('avg_cost_per_run', 0):.4f}")
            logger.info(f"  Avg tokens: {stats['avg_input_tokens']:.0f} in / {stats['avg_output_tokens']:.0f} out")
        
        logger.info(f"\nSummary saved to: {summary_path}")


    def test_all_models_comparison(self):
        """Run comprehensive comparison of all model combinations"""
        logger.info("\n=== COMPREHENSIVE MODEL COMPARISON TEST ===\n")
        
        # Test cases to run
        test_cases = [
            {
                'name': 'Level 1: Single Flight',
                'data_path': 'level_1_single_booking/single_flight_booking.json',
                'data_key': 'emails',
                'is_single_email': True
            },
            {
                'name': 'Level 2: Multi Booking',
                'data_path': 'level_2_multi_booking/multi_booking_flight_hotel.json',
                'data_key': 'emails',
                'is_single_email': False
            },
            {
                'name': 'Level 5: Same Day Trips',
                'data_path': 'level_5_edge_cases/same_day_trips.json',
                'data_key': 'emails',
                'is_single_email': False
            }
        ]
        
        # Model combinations to test
        model_combinations = [
            ("gemini", "fast"),
            ("gemini", "powerful"),
            ("openai", "fast"),
            ("openai", "powerful"),
            ("claude", "fast"),
            ("claude", "powerful")
        ]
        
        # Results collection
        all_results = {}
        
        for test_case in test_cases:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing: {test_case['name']}")
            logger.info(f"{'='*60}\n")
            
            test_results = {}
            
            # Load test data
            test_data_path = os.path.join(
                os.path.dirname(__file__), 
                'test_data', 
                test_case['data_path']
            )
            with open(test_data_path, 'r') as f:
                test_data = json.load(f)
            
            if test_case['is_single_email']:
                # For Level 1, the data is a single email object
                emails = [test_data]
            else:
                # For other levels, emails are in an array
                emails = test_data[test_case['data_key']]
            
            # Test each model combination
            for provider_name, model_tier in model_combinations:
                model_key = f"{provider_name}_{model_tier}"
                
                try:
                    logger.info(f"Testing {model_key}...")
                    
                    # Create AI provider
                    ai_provider = AIProviderFactory.create_provider(
                        model_tier=model_tier,
                        provider_name=provider_name
                    )
                    
                    # Run detection
                    detector = TripDetector(ai_provider)
                    prompt = detector._create_trip_detection_prompt(emails, [])
                    
                    start_time = datetime.now()
                    ai_response = ai_provider.generate_content(prompt)
                    response_time = (datetime.now() - start_time).total_seconds()
                    
                    detected_trips = detector._parse_ai_response(ai_response['content'], emails)
                    
                    # Store results
                    test_results[model_key] = {
                        'success': True,
                        'trips_count': len(detected_trips),
                        'trips': detected_trips,
                        'response_time': response_time,
                        'input_tokens': ai_response['input_tokens'],
                        'output_tokens': ai_response['output_tokens'],
                        'cost': ai_response['estimated_cost_usd'],
                        'error': None
                    }
                    
                    # Log to test runs file
                    self.log_test_run(
                        provider_name=provider_name,
                        model_tier=model_tier,
                        input_text=prompt,
                        output_text=ai_response['content'],
                        input_tokens=ai_response['input_tokens'],
                        output_tokens=ai_response['output_tokens'],
                        total_cost=ai_response['estimated_cost_usd'],
                        success=True,
                        error_msg=None
                    )
                    
                    logger.info(f"✓ {model_key}: {len(detected_trips)} trips, "
                              f"${ai_response['estimated_cost_usd']:.6f}, "
                              f"{response_time:.1f}s")
                    
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    test_results[model_key] = {
                        'success': False,
                        'error': error_msg,
                        'trips_count': 0,
                        'response_time': 0,
                        'cost': 0
                    }
                    
                    # Log failure
                    self.log_test_run(
                        provider_name=provider_name,
                        model_tier=model_tier,
                        input_text="",
                        output_text="",
                        input_tokens=0,
                        output_tokens=0,
                        total_cost=0.0,
                        success=False,
                        error_msg=error_msg
                    )
                    
                    logger.error(f"✗ {model_key}: {error_msg}")
            
            all_results[test_case['name']] = test_results
            
            # Compare results for this test case
            self._compare_test_results(test_case['name'], test_results)
        
        # Generate comprehensive report
        self._generate_comparison_report(all_results)
    
    def _compare_test_results(self, test_name: str, results: Dict):
        """Compare results across models for a specific test"""
        logger.info(f"\n--- Comparison for {test_name} ---")
        
        successful_results = {k: v for k, v in results.items() if v['success']}
        
        if not successful_results:
            logger.warning("No successful results to compare")
            return
        
        # Trip count consistency
        trip_counts = {k: v['trips_count'] for k, v in successful_results.items()}
        unique_counts = set(trip_counts.values())
        
        if len(unique_counts) == 1:
            logger.info(f"✓ All models agree on trip count: {list(unique_counts)[0]}")
        else:
            logger.warning(f"⚠ Models disagree on trip count: {trip_counts}")
        
        # Cost comparison
        costs = [(k, v['cost']) for k, v in successful_results.items()]
        costs.sort(key=lambda x: x[1])
        
        logger.info("\nCost ranking (cheapest to most expensive):")
        for i, (model, cost) in enumerate(costs):
            if i == 0:
                logger.info(f"  1. {model}: ${cost:.6f} (baseline)")
            else:
                ratio = cost / costs[0][1]
                logger.info(f"  {i+1}. {model}: ${cost:.6f} ({ratio:.1f}x)")
        
        # Speed comparison
        speeds = [(k, v['response_time']) for k, v in successful_results.items()]
        speeds.sort(key=lambda x: x[1])
        
        logger.info("\nSpeed ranking (fastest to slowest):")
        for i, (model, time) in enumerate(speeds):
            logger.info(f"  {i+1}. {model}: {time:.1f}s")
        
        # Quality indicators
        logger.info("\nQuality indicators:")
        for model, result in successful_results.items():
            if result['trips_count'] > 0:
                trip = result['trips'][0]
                has_accommodations = len(trip.get('accommodations', [])) > 0
                has_activities = len(trip.get('tour_activities', [])) > 0
                segments_count = len(trip.get('transport_segments', []))
                
                logger.info(f"  {model}: {segments_count} segments, "
                          f"{'✓' if has_accommodations else '✗'} accommodations, "
                          f"{'✓' if has_activities else '✗'} activities")
    
    def _generate_comparison_report(self, all_results: Dict):
        """Generate final comparison report"""
        logger.info("\n" + "="*80)
        logger.info("FINAL COMPARISON REPORT")
        logger.info("="*80 + "\n")
        
        # Overall statistics
        total_tests = 0
        total_success = 0
        total_cost = 0.0
        
        model_stats = {}
        
        for test_name, test_results in all_results.items():
            for model, result in test_results.items():
                if model not in model_stats:
                    model_stats[model] = {
                        'tests': 0,
                        'successes': 0,
                        'total_cost': 0.0,
                        'total_time': 0.0
                    }
                
                model_stats[model]['tests'] += 1
                total_tests += 1
                
                if result['success']:
                    model_stats[model]['successes'] += 1
                    model_stats[model]['total_cost'] += result['cost']
                    model_stats[model]['total_time'] += result['response_time']
                    total_success += 1
                    total_cost += result['cost']
        
        # Model performance summary
        logger.info("Model Performance Summary:")
        logger.info(f"{'Model':<20} {'Success Rate':<15} {'Avg Cost':<12} {'Avg Time':<10}")
        logger.info("-" * 60)
        
        for model, stats in sorted(model_stats.items()):
            success_rate = stats['successes'] / stats['tests'] * 100 if stats['tests'] > 0 else 0
            avg_cost = stats['total_cost'] / stats['successes'] if stats['successes'] > 0 else 0
            avg_time = stats['total_time'] / stats['successes'] if stats['successes'] > 0 else 0
            
            logger.info(f"{model:<20} {success_rate:>6.1f}%        "
                      f"${avg_cost:>8.6f}    {avg_time:>6.1f}s")
        
        logger.info(f"\nTotal tests run: {total_tests}")
        logger.info(f"Total successful: {total_success}")
        logger.info(f"Total cost: ${total_cost:.6f}")
        
        # Save detailed results
        report_path = Path(__file__).parent / "test_data" / "model_comparison_report.json"
        with open(report_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': all_results,
                'summary': model_stats
            }, f, indent=2)
        
        logger.info(f"\nDetailed report saved to: {report_path}")


if __name__ == "__main__":
    # Run tests with pytest
    result = pytest.main([__file__, "-v", "-s"])
    
    # Generate summary after tests
    test_instance = TestTripDetector()
    test_instance.generate_test_summary()