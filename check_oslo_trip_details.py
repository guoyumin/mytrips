#!/usr/bin/env python3
"""
Extract Oslo trip details from log file
"""
import re
import json

def extract_oslo_trip_data():
    """Extract Oslo trip data from logs"""
    with open('logs/server.log', 'r') as f:
        content = f.read()
    
    # Find Oslo trip JSON data
    pattern = r'"name": "Trip to Oslo".*?(?=\n2025-07-13|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    print(f"Found {len(matches)} Oslo trip occurrences\n")
    
    for i, match in enumerate(matches[-2:]):  # Show last 2 occurrences
        print(f"\n=== Occurrence {i+1} ===")
        
        # Try to extract the full JSON
        # Find the opening brace before "name"
        start_pos = match.find('"name"')
        if start_pos > 0:
            # Count braces to find complete JSON
            brace_count = 0
            in_string = False
            escape_next = False
            json_start = -1
            
            # Look backwards for opening brace
            for j in range(start_pos, -1, -1):
                if match[j] == '{' and not in_string:
                    json_start = j
                    break
            
            if json_start >= 0:
                # Now extract the complete JSON
                json_str = ""
                brace_count = 0
                in_string = False
                escape_next = False
                
                for char in match[json_start:]:
                    json_str += char
                    
                    if escape_next:
                        escape_next = False
                        continue
                        
                    if char == '\\':
                        escape_next = True
                        continue
                        
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                break
                
                try:
                    trip_data = json.loads(json_str)
                    print(json.dumps(trip_data, indent=2))
                    
                    # Extract email IDs if present
                    if 'related_emails' in trip_data:
                        print(f"\nRelated emails: {trip_data['related_emails']}")
                    
                    # Check transport segments
                    if 'transport_segments' in trip_data:
                        print(f"\nTransport segments: {len(trip_data['transport_segments'])}")
                        for seg in trip_data['transport_segments']:
                            print(f"  - {seg.get('segment_type')}: {seg.get('departure_location')} -> {seg.get('arrival_location')}")
                            print(f"    Departure: {seg.get('departure_datetime')}")
                            print(f"    Arrival: {seg.get('arrival_datetime')}")
                            if 'related_emails' in seg:
                                print(f"    Related emails: {seg.get('related_emails')}")
                    
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON: {e}")
                    print(f"JSON string (first 500 chars): {json_str[:500]}...")

if __name__ == "__main__":
    extract_oslo_trip_data()