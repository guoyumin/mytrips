from datetime import datetime
from backend.models.trip import Trip

def verify_fix():
    # Create a dummy trip data with datetime objects (simulating existing trip from DB)
    trip_data = {
        "name": "Test Trip",
        "start_date": datetime(2023, 6, 30),
        "end_date": datetime(2023, 7, 1),
        "accommodations": [
            {
                "property_name": "Test Hotel",
                "check_in_date": datetime(2023, 6, 30, 14, 0),
                "check_out_date": datetime(2023, 7, 1, 11, 0)
            }
        ]
    }
    
    print("Attempting to create Trip from data with datetime objects...")
    try:
        trip = Trip.from_json(trip_data)
        print("SUCCESS: Trip created successfully!")
        print(f"Check-in date type: {type(trip.accommodations[0].check_in_date)}")
    except Exception as e:
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    verify_fix()
