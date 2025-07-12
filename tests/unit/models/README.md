# Unit Tests for Domain Models

This directory contains comprehensive unit tests for the Trip and BookingInfo domain models, focusing on JSON parsing and validation which are the most error-prone areas.

## Test Coverage

### Trip Model Tests (`test_trip.py`)
- **Basic JSON Parsing**: Valid trip parsing, missing required fields, empty bookings
- **Date Validation**: Date order validation, date format parsing
- **Segment Validation**: Transport segments, accommodations, activities, cruises
- **Type Normalization**: Segment types, status values, distance types
- **Cost Calculation**: Automatic total cost calculation from segments
- **Complex Scenarios**: Multi-segment trips with all booking types
- **JSON String Parsing**: String input handling and error cases

### BookingInfo Model Tests (`test_booking.py`)
- **Basic JSON Parsing**: Valid bookings, non-booking emails, enum conversions
- **Completeness Validation**: Required fields for each booking type
- **Location Detection**: Zurich local trip identification
- **Test Booking Detection**: Identifying test/demo bookings
- **Trip Detection Validation**: Complete validation pipeline
- **Data Aggregation**: Confirmation numbers, date ranges, total costs
- **Complex Scenarios**: Multi-segment bookings, cancellations, modifications
- **Edge Cases**: Empty bookings, partial dates, malformed data

## Running the Tests

From the backend directory:
```bash
# Run all model tests
python -m pytest ../tests/unit/models/ -v

# Run specific test file
python -m pytest ../tests/unit/models/test_trip.py -v
python -m pytest ../tests/unit/models/test_booking.py -v

# Run with coverage
python -m pytest ../tests/unit/models/ --cov=models --cov-report=html
```

## Key Test Patterns

1. **Validation Testing**: Each test validates both positive and negative cases
2. **Data Transformation**: Tests ensure data is correctly transformed between formats
3. **Business Logic**: Tests verify domain-specific rules (e.g., local trip detection)
4. **Error Handling**: Tests ensure graceful handling of invalid or incomplete data
5. **Edge Cases**: Tests cover boundary conditions and unusual scenarios

## Test Organization

Tests are organized into classes by functionality:
- `TestJSONParsing`: Basic parsing and validation
- `TestComplexScenarios`: Real-world use cases
- `TestEdgeCases`: Boundary conditions and error handling

This structure makes it easy to find and add tests for specific functionality.