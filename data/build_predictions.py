#!/usr/bin/env python3
"""
Build prediction model from Toronto Bike Share historical ridership data.
Creates a JSON lookup file with patterns by station, day of week, and hour.
"""

import csv
import json
import os
from datetime import datetime
from collections import defaultdict
from glob import glob

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(DATA_DIR, "station_patterns.json")

# Stations near our target locations (we'll expand this after seeing what stations are in the data)
TARGET_STATIONS = {
    # Near 215 Fort York Blvd
    "fort_york": ["7000", "7366", "7751", "7681", "7076"],
    # Near 155 Wellington St (RBC)
    "wellington": ["7052", "7053", "7054", "7082", "7081"]
}


def parse_datetime(dt_str):
    """Parse datetime from CSV format."""
    # Format: "01/01/2024 00:00" or "1/1/2024 0:00"
    for fmt in ["%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M"]:
        try:
            return datetime.strptime(dt_str.strip(), fmt)
        except ValueError:
            continue
    return None


def process_csv_file(filepath, departures, arrivals):
    """Process a single CSV file and update departure/arrival counts."""
    print(f"Processing: {os.path.basename(filepath)}")
    
    with open(filepath, 'r', encoding='latin-1') as f:
        reader = csv.DictReader(f)
        
        row_count = 0
        for row in reader:
            row_count += 1
            
            # Parse start time for departures
            start_time = parse_datetime(row.get('Start Time', ''))
            start_station = row.get('Start Station Id', '').strip()
            
            if start_time and start_station:
                day_of_week = start_time.weekday()  # 0=Monday, 6=Sunday
                hour = start_time.hour
                departures[start_station][(day_of_week, hour)] += 1
            
            # Parse end time for arrivals
            end_time = parse_datetime(row.get('End Time', ''))
            end_station = row.get('End Station Id', '').strip()
            
            if end_time and end_station:
                day_of_week = end_time.weekday()
                hour = end_time.hour
                arrivals[end_station][(day_of_week, hour)] += 1
        
        print(f"  Processed {row_count:,} trips")


def calculate_patterns(departures, arrivals):
    """Calculate patterns for each station."""
    patterns = {}
    
    # Get all unique stations
    all_stations = set(departures.keys()) | set(arrivals.keys())
    
    for station_id in all_stations:
        station_pattern = {
            "departures": {},
            "arrivals": {},
            "net_flow": {},  # Positive = more bikes arriving, Negative = more bikes leaving
            "depletion_risk": {}  # Hours when station typically runs low
        }
        
        for day in range(7):  # 0-6 (Mon-Sun)
            day_name = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][day]
            station_pattern["departures"][day_name] = {}
            station_pattern["arrivals"][day_name] = {}
            station_pattern["net_flow"][day_name] = {}
            
            cumulative_flow = 0
            min_cumulative = 0
            min_hour = 0
            
            for hour in range(24):
                dep = departures[station_id].get((day, hour), 0)
                arr = arrivals[station_id].get((day, hour), 0)
                net = arr - dep  # Positive = gaining bikes
                
                station_pattern["departures"][day_name][str(hour)] = dep
                station_pattern["arrivals"][day_name][str(hour)] = arr
                station_pattern["net_flow"][day_name][str(hour)] = net
                
                # Track cumulative flow to find when station typically depletes
                cumulative_flow += net
                if cumulative_flow < min_cumulative:
                    min_cumulative = cumulative_flow
                    min_hour = hour
            
            # Record depletion risk (hour when cumulative outflow is worst)
            if min_cumulative < -10:  # Significant depletion
                station_pattern["depletion_risk"][day_name] = {
                    "hour": min_hour,
                    "severity": abs(min_cumulative)
                }
        
        patterns[station_id] = station_pattern
    
    return patterns


def main():
    print("Building bike share prediction model...")
    print("=" * 50)
    
    # Find all CSV files
    csv_files = sorted(glob(os.path.join(DATA_DIR, "Bike share ridership *.csv")))
    
    if not csv_files:
        print("No CSV files found!")
        return
    
    print(f"Found {len(csv_files)} data files")
    
    # Aggregate departures and arrivals by station and time
    # Structure: {station_id: {(day_of_week, hour): count}}
    departures = defaultdict(lambda: defaultdict(int))
    arrivals = defaultdict(lambda: defaultdict(int))
    
    for csv_file in csv_files:
        process_csv_file(csv_file, departures, arrivals)
    
    print("\n" + "=" * 50)
    print("Calculating patterns...")
    
    patterns = calculate_patterns(departures, arrivals)
    
    # Count weeks of data for averaging
    # Approximate: 9 months of data = ~39 weeks
    weeks_of_data = 39
    
    # Calculate averages per week
    for station_id, pattern in patterns.items():
        for day_name in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
            for hour in range(24):
                hour_str = str(hour)
                if hour_str in pattern["departures"].get(day_name, {}):
                    pattern["departures"][day_name][hour_str] = round(
                        pattern["departures"][day_name][hour_str] / weeks_of_data, 1
                    )
                if hour_str in pattern["arrivals"].get(day_name, {}):
                    pattern["arrivals"][day_name][hour_str] = round(
                        pattern["arrivals"][day_name][hour_str] / weeks_of_data, 1
                    )
                if hour_str in pattern["net_flow"].get(day_name, {}):
                    pattern["net_flow"][day_name][hour_str] = round(
                        pattern["net_flow"][day_name][hour_str] / weeks_of_data, 1
                    )
    
    # Add metadata
    output = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "data_source": "Toronto Bike Share Ridership 2024 (Jan-Sep)",
            "weeks_of_data": weeks_of_data,
            "total_stations": len(patterns)
        },
        "patterns": patterns
    }
    
    # Save to JSON
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nSaved patterns for {len(patterns)} stations to:")
    print(f"  {OUTPUT_FILE}")
    
    # Show sample for stations near our locations
    print("\n" + "=" * 50)
    print("Sample patterns for nearby stations:")
    
    sample_stations = ["7000", "7052"]  # Fort York / Wellington
    for station_id in sample_stations:
        if station_id in patterns:
            p = patterns[station_id]
            print(f"\nStation {station_id}:")
            print(f"  Friday 8am: departures={p['departures']['fri'].get('8', 0)}/wk, "
                  f"arrivals={p['arrivals']['fri'].get('8', 0)}/wk, "
                  f"net={p['net_flow']['fri'].get('8', 0)}/wk")
            if 'fri' in p.get('depletion_risk', {}):
                risk = p['depletion_risk']['fri']
                print(f"  Depletion risk: typically lowest around {risk['hour']}:00")


if __name__ == "__main__":
    main()
