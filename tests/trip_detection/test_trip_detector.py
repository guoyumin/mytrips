"""
Optimized Trip Detector Integration Tests

Tests the TripDetector class with all AI providers efficiently.
Each test case + provider combination is a separate pytest test.
"""
import pytest
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from lib.trip_detector import TripDetector
from lib.ai.ai_provider_factory import AIProviderFactory
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define all provider/model combinations to test
PROVIDER_COMBINATIONS = [
    ("gemini", "fast"),
    ("gemini", "powerful"),
    ("openai", "fast"),
    ("openai", "powerful"),
    ("claude", "fast"),
    ("claude", "powerful"),
    ("gemma3", "fast"),
    ("gemma3", "powerful"),
    ("deepseek", "fast"),
    ("deepseek", "powerful")
]

# Define all test cases
TEST_CASES = [
    {
        'id': 'single_flight',
        'name': 'Level 1: Single Flight',
        'data_path': 'level_1_single_booking/single_flight_booking.json',
        'expected_path': 'level_1_single_booking/expected_trip_output.json',
        'is_single_email': True,
        'validations': {
            'trip_count': 1,
            'has_transport': True,
            'has_accommodation': False,
            'has_activities': False
        }
    },
    {
        'id': 'multi_booking',
        'name': 'Level 2: Multi Booking (Flight + Hotel)',
        'data_path': 'level_2_multi_booking/multi_booking_flight_hotel.json',
        'is_single_email': False,
        'validations': {
            'trip_count': 1,
            'has_transport': True,
            'has_accommodation': True,
            'has_activities': False,
            'expected_destination': 'Barcelona',
            'expected_segments': 3
        }
    },
    {
        'id': 'add_activity',
        'name': 'Level 3: Add Activity to Existing Trip',
        'data_path': 'level_3_existing_trips/new_louvre_booking.json',
        'existing_trip_path': 'level_3_existing_trips/existing_paris_trip.json',
        'is_single_email': False,
        'validations': {
            'trip_count': 1,
            'has_activities': True,
            'expected_destination': 'Paris',
            'activity_contains': 'Louvre'
        }
    },
    {
        'id': 'same_day_trips',
        'name': 'Level 5: Same Day Multiple Trips',
        'data_path': 'level_5_edge_cases/same_day_trips.json',
        'is_single_email': False,
        'validations': {
            'trip_count': 2,
            'has_same_day_trip': True,
            'expected_destinations': ['Munich', 'Milan']
        }
    }
]


class TestTripDetectorIndividual:
    """Individual test cases for each provider/model/test combination"""
    
    @classmethod
    def setup_class(cls):
        """Setup test data storage"""
        cls._test_results = defaultdict(dict)
        
        # Setup log path
        cls.log_path = Path(__file__).parent / "test_data" / "optimized_test_runs.jsonl"
        cls.log_path.parent.mkdir(exist_ok=True)
    
    @staticmethod
    def log_test_run(test_case: str, provider: str, model_tier: str, 
                     success: bool, cost: float, tokens: Dict, time_taken: float,
                     error: Optional[str] = None):
        """Log test run details"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "test_case": test_case,
            "provider": provider,
            "model_tier": model_tier,
            "success": success,
            "cost_usd": cost,
            "input_tokens": tokens.get('input', 0),
            "output_tokens": tokens.get('output', 0),
            "total_tokens": tokens.get('total', 0),
            "response_time_seconds": time_taken,
            "error": error
        }
        
        log_path = Path(__file__).parent / "test_data" / "optimized_test_runs.jsonl"
        with open(log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    @staticmethod
    def load_test_data(test_case: Dict) -> Tuple[List[Dict], List[Dict]]:
        """Load test data for a test case"""
        base_path = Path(__file__).parent / 'test_data'
        
        # Load main test data
        with open(base_path / test_case['data_path'], 'r') as f:
            test_data = json.load(f)
        
        if test_case['is_single_email']:
            emails = [test_data]
        else:
            emails = test_data.get('emails', test_data.get('new_emails', []))
        
        # Load existing trips if specified
        existing_trips = []
        if test_case.get('existing_trip_path'):
            with open(base_path / test_case['existing_trip_path'], 'r') as f:
                existing_data = json.load(f)
                existing_trips = existing_data.get('existing_trips', [])
        
        return emails, existing_trips
    
    @staticmethod
    def validate_trip_structure(trip: Dict) -> None:
        """Validate that a trip has all required fields"""
        required_fields = [
            'name', 'destination', 'start_date', 'end_date',
            'cities_visited', 'total_cost', 'transport_segments',
            'accommodations', 'tour_activities', 'cruises'
        ]
        
        for field in required_fields:
            assert field in trip, f"Trip missing required field: {field}"
    
    @staticmethod
    def validate_test_case(trips: List[Dict], validations: Dict) -> None:
        """Validate trips against test case expectations"""
        # Trip count
        if 'trip_count' in validations:
            assert len(trips) == validations['trip_count'], \
                f"Expected {validations['trip_count']} trips, got {len(trips)}"
        
        # Check for specific components
        if validations.get('has_transport'):
            assert any(len(trip.get('transport_segments', [])) > 0 for trip in trips), \
                "Expected transport segments"
        
        if validations.get('has_accommodation'):
            assert any(len(trip.get('accommodations', [])) > 0 for trip in trips), \
                "Expected accommodations"
        
        if validations.get('has_activities'):
            assert any(len(trip.get('tour_activities', [])) > 0 for trip in trips), \
                "Expected activities"
        
        # Specific expectations
        if 'expected_destination' in validations:
            destinations = [trip.get('destination') for trip in trips]
            assert validations['expected_destination'] in destinations, \
                f"Expected destination {validations['expected_destination']}, got {destinations}"
        
        if 'expected_segments' in validations:
            total_segments = sum(len(trip.get('transport_segments', [])) for trip in trips)
            assert total_segments == validations['expected_segments'], \
                f"Expected {validations['expected_segments']} segments, got {total_segments}"
        
        if 'activity_contains' in validations:
            activities = []
            for trip in trips:
                activities.extend([a.get('activity_name', '') for a in trip.get('tour_activities', [])])
            assert any(validations['activity_contains'] in activity for activity in activities), \
                f"Expected activity containing '{validations['activity_contains']}'"
        
        if validations.get('has_same_day_trip'):
            assert any(trip['start_date'] == trip['end_date'] for trip in trips), \
                "Expected at least one same-day trip"


# Generate individual test methods dynamically
def generate_test_method(test_case, provider_name, model_tier):
    """Generate a test method for a specific combination"""
    def test_method(self):
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing: {test_case['name']} with {provider_name}-{model_tier}")
        logger.info('='*80)
        
        # Load test data
        emails, existing_trips = self.load_test_data(test_case)
        
        try:
            # Create AI provider
            ai_provider = AIProviderFactory.create_provider(
                model_tier=model_tier,
                provider_name=provider_name
            )
            
            # Create detector and prepare prompt
            detector = TripDetector(ai_provider)
            prompt = detector._create_trip_detection_prompt(emails, existing_trips)
            
            # Time the AI call
            start_time = datetime.now()
            ai_response = ai_provider.generate_content(prompt)
            response_time = (datetime.now() - start_time).total_seconds()
            
            # Parse trips
            detected_trips = detector._parse_ai_response(ai_response['content'], emails)
            
            # Store result
            result = {
                'success': True,
                'trips': detected_trips,
                'input_tokens': ai_response['input_tokens'],
                'output_tokens': ai_response['output_tokens'],
                'total_tokens': ai_response['total_tokens'],
                'cost': ai_response['estimated_cost_usd'],
                'response_time': response_time,
                'prompt_length': len(prompt),
                'response_length': len(ai_response['content'])
            }
            
            # Validate structure and expectations
            for trip in detected_trips:
                self.validate_trip_structure(trip)
            
            self.validate_test_case(detected_trips, test_case.get('validations', {}))
            
            # Log success
            self.log_test_run(
                test_case['name'], provider_name, model_tier,
                success=True, cost=result['cost'],
                tokens={'input': result['input_tokens'], 'output': result['output_tokens'], 
                       'total': result['total_tokens']},
                time_taken=result['response_time']
            )
            
            # Store for later analysis
            self._test_results[test_case['name']][f"{provider_name}_{model_tier}"] = result
            
            # Log summary
            cost_str = f"${result['cost']:.6f}" if provider_name not in ['gemma3', 'deepseek'] else "$0.00 (local)"
            logger.info(f"✓ Success: {len(detected_trips)} trips, {cost_str}, "
                      f"{result['response_time']:.1f}s, "
                      f"{result['total_tokens']:,} tokens")
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            # Store failure
            self._test_results[test_case['name']][f"{provider_name}_{model_tier}"] = {
                'success': False,
                'error': error_msg
            }
            
            # Log failure
            self.log_test_run(
                test_case['name'], provider_name, model_tier,
                success=False, cost=0, tokens={}, time_taken=0,
                error=error_msg
            )
            
            logger.error(f"✗ Failed: {error_msg}")
            
            # Skip provider if not configured
            if "Could not create" in error_msg or "not configured" in error_msg:
                pytest.skip(f"Provider {provider_name} not configured")
            else:
                # Re-raise for proper test failure
                raise
    
    return test_method


# Add test methods to the class
for test_case in TEST_CASES:
    for provider_name, model_tier in PROVIDER_COMBINATIONS:
        # Create unique test method name
        test_name = f"test_{test_case['id']}_{provider_name}_{model_tier}"
        
        # Generate and add the test method
        test_method = generate_test_method(test_case, provider_name, model_tier)
        test_method.__name__ = test_name
        setattr(TestTripDetectorIndividual, test_name, test_method)


class TestTripDetectorSummary:
    """Generate summary report after all individual tests"""
    
    def test_generate_summary_report(self):
        """Generate comprehensive comparison after all tests"""
        # This test should run last - we use pytest ordering or naming convention
        test_results = getattr(TestTripDetectorIndividual, '_test_results', {})
        
        if not test_results:
            pytest.skip("No test results to summarize")
        
        logger.info("\n" + "="*80)
        logger.info("COMPREHENSIVE TEST RESULTS SUMMARY")
        logger.info("="*80)
        
        # Overall statistics
        total_tests = 0
        total_success = 0
        total_failures = 0
        total_cost = 0.0
        provider_stats = defaultdict(lambda: {
            'tests': 0, 'successes': 0, 'failures': 0,
            'total_cost': 0.0, 'total_time': 0.0, 'total_tokens': 0
        })
        
        # Process all results
        for test_case_name, provider_results in test_results.items():
            logger.info(f"\n{test_case_name}:")
            logger.info("-" * len(test_case_name))
            
            # Analyze results for this test case
            successful_results = {k: v for k, v in provider_results.items() if v.get('success', False)}
            failed_results = {k: v for k, v in provider_results.items() if not v.get('success', False)}
            
            if successful_results:
                # Trip count consistency
                trip_counts = {k: len(v['trips']) for k, v in successful_results.items()}
                unique_counts = set(trip_counts.values())
                
                if len(unique_counts) == 1:
                    logger.info(f"✓ All successful models agree: {list(unique_counts)[0]} trip(s)")
                else:
                    logger.info(f"⚠ Trip count varies: {trip_counts}")
                
                # Cost ranking
                costs = [(k, v['cost']) for k, v in successful_results.items()]
                costs.sort(key=lambda x: x[1])
                
                logger.info("\nCost ranking (successful runs):")
                for i, (model, cost) in enumerate(costs):
                    if any(local in model for local in ['gemma3', 'deepseek']):
                        logger.info(f"  {i+1}. {model}: $0.0000 (local)")
                    else:
                        logger.info(f"  {i+1}. {model}: ${cost:.6f}")
            
            if failed_results:
                logger.info(f"\n❌ Failed: {list(failed_results.keys())}")
            
            # Update statistics
            for provider_key, result in provider_results.items():
                provider_name = provider_key.split('_')[0]
                stats = provider_stats[provider_name]
                stats['tests'] += 1
                total_tests += 1
                
                if result.get('success', False):
                    stats['successes'] += 1
                    stats['total_cost'] += result.get('cost', 0)
                    stats['total_time'] += result.get('response_time', 0)
                    stats['total_tokens'] += result.get('total_tokens', 0)
                    total_success += 1
                    total_cost += result.get('cost', 0)
                else:
                    stats['failures'] += 1
                    total_failures += 1
        
        # Provider summary
        logger.info("\n" + "="*80)
        logger.info("PROVIDER SUMMARY")
        logger.info("="*80)
        
        logger.info(f"\n{'Provider':<15} {'Tests':<10} {'Success':<10} {'Failed':<10} "
                   f"{'Avg Cost':<12} {'Avg Time':<10} {'Total Tokens':<15}")
        logger.info("-" * 90)
        
        for provider, stats in sorted(provider_stats.items()):
            success_rate = f"{stats['successes']}/{stats['tests']}"
            avg_cost = stats['total_cost'] / stats['successes'] if stats['successes'] > 0 else 0
            avg_time = stats['total_time'] / stats['successes'] if stats['successes'] > 0 else 0
            
            cost_str = "$0.0000" if provider in ['gemma3', 'deepseek'] else f"${avg_cost:.6f}"
            
            logger.info(f"{provider:<15} {stats['tests']:<10} {success_rate:<10} "
                       f"{stats['failures']:<10} "
                       f"{cost_str:<12} {avg_time:<10.1f}s {stats['total_tokens']:<15,}")
        
        # Final summary
        logger.info(f"\nTotal tests run: {total_tests}")
        logger.info(f"Total successful: {total_success}")
        logger.info(f"Total failed: {total_failures}")
        logger.info(f"Total API cost: ${total_cost:.6f}")
        
        # Save detailed report
        report_path = Path(__file__).parent / "test_data" / "optimized_test_report.json"
        with open(report_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': dict(test_results),
                'provider_stats': dict(provider_stats),
                'total_tests': total_tests,
                'total_success': total_success,
                'total_failures': total_failures,
                'total_cost': total_cost
            }, f, indent=2)
        
        logger.info(f"\nDetailed report saved to: {report_path}")
        
        # This is just a summary, not a test assertion
        assert True


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])