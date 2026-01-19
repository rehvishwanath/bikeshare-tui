#!/usr/bin/env python3
"""
Toronto Bike Share TUI with Predictions
A beautiful terminal interface showing available bikes and docks near specified locations,
with historical pattern-based predictions for likelihood of finding bikes/docks.
"""

import urllib.request
import urllib.parse
import json
import math
import os
import sys
import argparse
import time
from datetime import datetime
from typing import Optional
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.align import Align
from rich.live import Live

# API endpoints
STATION_INFO_URL = "https://tor.publicbikesystem.net/ube/gbfs/v1/en/station_information"
STATION_STATUS_URL = "https://tor.publicbikesystem.net/ube/gbfs/v1/en/station_status"

# Path to prediction data (resolve symlink to get actual script location)
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
PREDICTIONS_FILE = os.path.join(SCRIPT_DIR, "..", "data", "station_patterns.json")

# Target locations (approximate coordinates)
LOCATIONS = {
    "215 Fort York Blvd": {
        "lat": 43.6375,
        "lon": -79.4030,
        "emoji": "🏠"
    },
    "155 Wellington St (RBC Centre)": {
        "lat": 43.6458,
        "lon": -79.3854,
        "emoji": "🏢"
    }
}

# How many nearby stations to show in the list
NUM_NEARBY_STATIONS = 5
# How many closest stations to use for calculating predictions/warnings
# (Restricted to closest 2 to avoid averaging out specific location data)
NUM_PREDICTION_STATIONS = 2
# Absolute floor: minimum bikes to avoid LOW rating regardless of percentage
# (Accounts for ~10% damaged bikes + buffer for others grabbing bikes)
ABSOLUTE_BIKE_FLOOR = 5
ABSOLUTE_DOCK_FLOOR = 5

# Trip confidence calculation
TRIP_BIKE_WEIGHT = 0.6  # Bikes are more important (gating factor)
TRIP_DOCK_WEIGHT = 0.4  # Docks matter less (can ride to nearby station)
TRIP_HIGH_THRESHOLD = 2.5
TRIP_MEDIUM_THRESHOLD = 1.8

# "Leave by" calculation
LEAVE_BY_BUFFER_MINUTES = 30  # Buffer time before hitting the floor
LEAVE_BY_MAX_HOURS = 1  # Only show "leave by" if within this many hours

# Day name mapping
DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_FULL_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Config
CONFIG_FILE = os.path.expanduser("~/.bikes_config.json")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "TorontoBikeShareTUI/1.0"

console = Console()


def load_config() -> dict:
    """Load configuration from JSON file."""
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def save_config(locations: dict):
    """Save configuration to JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(locations, f, indent=4)
        console.print(f"[green]Configuration saved to {CONFIG_FILE}[/]")
    except Exception as e:
        console.print(f"[bold red]Error saving config:[/] {e}")


def geocode_address(query: str) -> Optional[dict]:
    """
    Geocode an address using OpenStreetMap Nominatim API.
    Returns dict with 'lat', 'lon', 'display_name' or None.
    """
    params = {
        'q': query,
        'format': 'json',
        'addressdetails': 1,
        'limit': 1,
        # Bias results towards Toronto
        'viewbox': '-79.63,43.58,-79.11,43.85',
        'bounded': 1
    }
    
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if not data:
                return None
            return data[0]
    except Exception as e:
        console.print(f"[bold red]Geocoding error:[/] {e}")
        return None


def format_address_result(result: dict) -> str:
    """
    Format the address result to be user-friendly.
    Extracts house_number, road, and postcode.
    """
    address = result.get('address', {})
    parts = []
    
    # Try to find specific parts
    house = address.get('house_number')
    road = address.get('road')
    postcode = address.get('postcode')
    building = address.get('building')
    
    if building:
        parts.append(building)
        
    if house and road:
        parts.append(f"{house} {road}")
    elif road:
        parts.append(road)
    elif result.get('display_name'):
        # Fallback to first few parts of display name
        return ", ".join(result['display_name'].split(", ")[:2])
        
    if postcode:
        parts.append(postcode)
        
    if not parts:
        return result.get('display_name', 'Unknown Location')
        
    return ", ".join(parts)


def run_setup_wizard() -> dict:
    """Run interactive setup wizard to configure locations."""
    console.print(Panel("[bold]🛠️  Bike Share Setup Wizard[/]", border_style="blue"))
    console.print("We'll find your exact location to show the closest stations.\n")
    
    locations = {}
    
    # 1. Home Location
    console.print("[bold cyan]Step 1: Home Location (Start of day)[/]")
    while True:
        query = console.input("Enter address (e.g. '215 Fort York Blvd'): ").strip()
        if not query:
            continue
            
        with console.status("Searching...", spinner="dots"):
            result = geocode_address(query)
            
        if not result:
            console.print("[red]Location not found. Please try again with more detail.[/]")
            continue
            
        formatted = format_address_result(result)
        console.print(f"Found: [bold green]{formatted}[/]")
        
        confirm = console.input("Is this correct? [Y/n] ").lower()
        if confirm == '' or confirm == 'y':
            locations["Home"] = {
                "lat": float(result['lat']),
                "lon": float(result['lon']),
                "emoji": "🏠",
                "address": formatted
            }
            break
    
    console.print()
    
    # 2. Work Location
    console.print("[bold cyan]Step 2: Work Location (End of day)[/]")
    while True:
        query = console.input("Enter address (e.g. '155 Wellington St W'): ").strip()
        if not query:
            continue
            
        with console.status("Searching...", spinner="dots"):
            result = geocode_address(query)
            
        if not result:
            console.print("[red]Location not found. Please try again with more detail.[/]")
            continue
            
        formatted = format_address_result(result)
        console.print(f"Found: [bold green]{formatted}[/]")
        
        confirm = console.input("Is this correct? [Y/n] ").lower()
        if confirm == '' or confirm == 'y':
            locations["Work"] = {
                "lat": float(result['lat']),
                "lon": float(result['lon']),
                "emoji": "🏢",
                "address": formatted
            }
            break
            
    save_config(locations)
    return locations


def load_predictions() -> dict:
    """Load prediction patterns from JSON file."""
    if not os.path.exists(PREDICTIONS_FILE):
        return None
    with open(PREDICTIONS_FILE, 'r') as f:
        return json.load(f)


def format_hour_12h(hour: int) -> str:
    """Format an hour (0-23) to 12-hour format (12 AM, 1 PM, etc.)."""
    if hour == 0:
        return "12 AM"
    elif hour == 12:
        return "12 PM"
    elif hour < 12:
        return f"{hour} AM"
    else:
        return f"{hour - 12} PM"


def fetch_json(url: str) -> dict:
    """Fetch JSON data from a URL."""
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode())


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth's radius in meters
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def get_station_data() -> tuple[dict, dict]:
    """Fetch station information and status from the API."""
    info_data = fetch_json(STATION_INFO_URL)
    status_data = fetch_json(STATION_STATUS_URL)
    
    # Create lookup dictionaries
    stations_info = {s["station_id"]: s for s in info_data["data"]["stations"]}
    stations_status = {s["station_id"]: s for s in status_data["data"]["stations"]}
    
    return stations_info, stations_status


def find_nearby_stations(target_lat: float, target_lon: float, 
                         stations_info: dict, stations_status: dict,
                         num_stations: int = 5) -> list:
    """Find the nearest stations to a given location."""
    stations_with_distance = []
    
    for station_id, info in stations_info.items():
        if station_id not in stations_status:
            continue
            
        status = stations_status[station_id]
        
        # Skip stations not in service
        if status.get("status") != "IN_SERVICE":
            continue
        
        distance = haversine_distance(
            target_lat, target_lon,
            info["lat"], info["lon"]
        )
        
        stations_with_distance.append({
            "id": station_id,
            "name": info["name"],
            "address": info.get("address", info["name"]),
            "lat": info["lat"],
            "lon": info["lon"],
            "capacity": info.get("capacity", 0),
            "is_charging": info.get("is_charging_station", False),
            "bikes_available": status.get("num_bikes_available", 0),
            "ebikes_available": status.get("num_ebikes_available", 0),
            "docks_available": status.get("num_docks_available", 0),
            "distance": distance
        })
    
    # Sort by distance and return top N
    stations_with_distance.sort(key=lambda x: x["distance"])
    return stations_with_distance[:num_stations]


def get_prediction_for_stations(nearby_stations: list, predictions: dict) -> dict:
    """
    Calculate bike and dock likelihood predictions for a set of nearby stations.
    Uses trend-adjusted logic combining current availability with historical patterns.
    """
    if not predictions or "patterns" not in predictions:
        return None
    
    patterns = predictions["patterns"]
    now = datetime.now()
    day_name = DAY_NAMES[now.weekday()]
    day_full = DAY_FULL_NAMES[now.weekday()]
    hour = now.hour
    hour_str = str(hour)
    
    # Aggregate metrics across nearby stations
    total_bikes = 0
    total_docks = 0
    total_capacity = 0
    total_net_flow_bikes = 0  # Positive = gaining bikes
    total_net_flow_docks = 0  # Positive = gaining docks (= losing bikes)
    
    bike_depletion_warnings = []
    dock_depletion_warnings = []
    
    # Only calculate predictions based on the closest few stations
    # to ensure warnings are relevant to the immediate location.
    prediction_stations = nearby_stations[:NUM_PREDICTION_STATIONS]
    
    for station in prediction_stations:
        station_id = station["id"]
        total_bikes += station["bikes_available"]
        total_docks += station["docks_available"]
        total_capacity += station["capacity"]
        
        if station_id in patterns:
            pattern = patterns[station_id]
            
            # Get net flow for current day/hour
            net_flow = pattern.get("net_flow", {}).get(day_name, {}).get(hour_str, 0)
            total_net_flow_bikes += net_flow  # Positive = more bikes arriving
            total_net_flow_docks -= net_flow  # Inverse for docks
            
            # Check for depletion risk
            depletion = pattern.get("depletion_risk", {}).get(day_name)
            if depletion:
                risk_hour = depletion["hour"]
                severity = depletion["severity"]
                # Only warn if depletion is coming up (within next 4 hours)
                if 0 < (risk_hour - hour) <= 4 and severity > 15:
                    bike_depletion_warnings.append({
                        "station": station["name"],
                        "hour": risk_hour,
                        "severity": severity
                    })
    
    # Calculate likelihood levels using TREND-ADJUSTED logic
    # HIGH: Current good AND trend stable/improving
    # MEDIUM: Current okay BUT trend worsening, OR current low but improving
    # LOW: Current low OR trend shows rapid depletion
    
    bike_pct = (total_bikes / total_capacity * 100) if total_capacity > 0 else 0
    dock_pct = (total_docks / total_capacity * 100) if total_capacity > 0 else 0
    
    # Bike likelihood
    if bike_pct >= 40 and total_net_flow_bikes >= -2:
        bike_likelihood = "HIGH"
    elif bike_pct >= 25 or (bike_pct >= 15 and total_net_flow_bikes > 0):
        bike_likelihood = "MEDIUM"
    else:
        bike_likelihood = "LOW"
    
    # Apply absolute floor: if enough bikes exist, never show LOW
    # (Accounts for damaged bikes and others grabbing bikes)
    if total_bikes >= ABSOLUTE_BIKE_FLOOR and bike_likelihood == "LOW":
        bike_likelihood = "MEDIUM"
    
    # Dock likelihood
    if dock_pct >= 40 and total_net_flow_docks >= -2:
        dock_likelihood = "HIGH"
    elif dock_pct >= 25 or (dock_pct >= 15 and total_net_flow_docks > 0):
        dock_likelihood = "MEDIUM"
    else:
        dock_likelihood = "LOW"
    
    # Apply absolute floor for docks
    if total_docks >= ABSOLUTE_DOCK_FLOOR and dock_likelihood == "LOW":
        dock_likelihood = "MEDIUM"
    
    # Generate depletion warning messages
    bike_warning = None
    dock_warning = None
    
    if bike_depletion_warnings:
        # Find earliest depletion
        earliest = min(bike_depletion_warnings, key=lambda x: x["hour"])
        bike_warning = f"Often runs low by {format_hour_12h(earliest['hour'])} on {day_full}s"
    
    # For docks, invert the logic - stations filling up means bikes arriving
    if total_net_flow_bikes > 5:  # Lots of bikes arriving = docks filling
        # Find when docks typically run out
        for station in prediction_stations:
            station_id = station["id"]
            if station_id in patterns:
                # Look ahead for when net flow becomes very positive (docks filling)
                pattern = patterns[station_id]
                for future_hour in range(hour + 1, min(hour + 5, 24)):
                    future_net = pattern.get("net_flow", {}).get(day_name, {}).get(str(future_hour), 0)
                    if future_net > 8:  # Heavy inflow
                        dock_warning = f"Fills up around {format_hour_12h(future_hour)} on {day_full}s"
                        break
    
    return {
        "bike_likelihood": bike_likelihood,
        "dock_likelihood": dock_likelihood,
        "bike_warning": bike_warning,
        "dock_warning": dock_warning,
        "net_flow_bikes": round(total_net_flow_bikes, 1),
        "net_flow_docks": round(total_net_flow_docks, 1),
        "day": day_full,
        "hour": hour
    }


def format_distance(meters: float) -> str:
    """Format distance in a human-readable way."""
    if meters < 1000:
        return f"{int(meters)}m"
    return f"{meters/1000:.1f}km"


def get_availability_style(available: int, capacity: int) -> str:
    """Get color style based on availability percentage."""
    if capacity == 0:
        return "white"
    ratio = available / capacity
    if ratio >= 0.5:
        return "bold green"
    elif ratio >= 0.25:
        return "bold yellow"
    elif ratio > 0:
        return "bold red"
    return "bold red reverse"


def get_bike_bar(bikes: int, ebikes: int, capacity: int, width: int = 20) -> Text:
    """Create a visual bar showing bike availability."""
    if capacity == 0:
        return Text("N/A", style="dim")
    
    bike_ratio = min(bikes / capacity, 1.0)
    ebike_ratio = min(ebikes / capacity, 1.0)
    
    bike_chars = int(bike_ratio * width)
    ebike_chars = int(ebike_ratio * width)
    empty_chars = width - bike_chars - ebike_chars
    
    bar = Text()
    bar.append("█" * bike_chars, style="blue")
    bar.append("█" * ebike_chars, style="cyan")
    bar.append("░" * empty_chars, style="dim")
    
    return bar


def get_dock_bar(docks: int, capacity: int, width: int = 20) -> Text:
    """Create a visual bar showing dock availability."""
    if capacity == 0:
        return Text("N/A", style="dim")
    
    dock_ratio = min(docks / capacity, 1.0)
    
    dock_chars = int(dock_ratio * width)
    empty_chars = width - dock_chars
    
    bar = Text()
    bar.append("█" * dock_chars, style="green")
    bar.append("░" * empty_chars, style="dim")
    
    return bar


def get_likelihood_style(likelihood: str) -> tuple[str, str]:
    """Get style and symbol for likelihood level."""
    if likelihood == "HIGH":
        return "bold green", "✓"
    elif likelihood == "MEDIUM":
        return "bold yellow", "⚠"
    else:
        return "bold red", "✗"


def likelihood_to_score(likelihood: str) -> int:
    """Convert likelihood string to numeric score."""
    return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(likelihood, 1)


def score_to_likelihood(score: float) -> str:
    """Convert numeric score back to likelihood string."""
    if score >= TRIP_HIGH_THRESHOLD:
        return "HIGH"
    elif score >= TRIP_MEDIUM_THRESHOLD:
        return "MEDIUM"
    else:
        return "LOW"


def calculate_trip_confidence(bike_likelihood: str, dock_likelihood: str) -> str:
    """
    Calculate overall trip confidence from bike and dock likelihoods.
    
    - Gating rule: LOW bikes = LOW trip (can't start without a bike)
    - Otherwise: weighted average (60% bikes, 40% docks)
    """
    # Gating rule: if bikes are LOW, trip is LOW regardless of docks
    if bike_likelihood == "LOW":
        return "LOW"
    
    # Weighted average
    bike_score = likelihood_to_score(bike_likelihood)
    dock_score = likelihood_to_score(dock_likelihood)
    trip_score = (bike_score * TRIP_BIKE_WEIGHT) + (dock_score * TRIP_DOCK_WEIGHT)
    
    return score_to_likelihood(trip_score)


def calculate_leave_by_time(current_bikes: int, net_flow_bikes: float, current_hour: int, current_minute: int) -> Optional[str]:
    """
    Calculate the "leave by" time based on current bikes and flow rate.
    
    Returns a formatted time string (e.g., "8:30 AM") or None if:
    - Net flow is not negative (bikes not depleting)
    - Leave by time is more than 1 hour away
    - Leave by time has already passed
    """
    # Only calculate if bikes are trending down
    if net_flow_bikes >= 0:
        return None
    
    # How many bikes above the floor?
    bikes_above_floor = current_bikes - ABSOLUTE_BIKE_FLOOR
    if bikes_above_floor <= 0:
        return None  # Already at or below floor
    
    # How long until we hit the floor?
    loss_rate = abs(net_flow_bikes)
    if loss_rate == 0:
        return None
    
    hours_until_floor = bikes_above_floor / loss_rate
    
    # Convert to minutes for easier calculation
    current_time_minutes = current_hour * 60 + current_minute
    depletion_time_minutes = current_time_minutes + (hours_until_floor * 60)
    leave_by_minutes = depletion_time_minutes - LEAVE_BY_BUFFER_MINUTES
    
    # Check if leave by time is in the past
    if leave_by_minutes <= current_time_minutes:
        return None  # Already passed
    
    # Check if leave by time is more than 1 hour away
    minutes_until_leave_by = leave_by_minutes - current_time_minutes
    if minutes_until_leave_by > LEAVE_BY_MAX_HOURS * 60:
        return None  # Too far in the future
    
    # Convert back to hours and minutes
    leave_by_hour = int(leave_by_minutes // 60) % 24
    leave_by_minute = int(leave_by_minutes % 60)
    
    # Format as 12-hour time
    if leave_by_hour == 0:
        time_str = f"12:{leave_by_minute:02d} AM"
    elif leave_by_hour == 12:
        time_str = f"12:{leave_by_minute:02d} PM"
    elif leave_by_hour < 12:
        time_str = f"{leave_by_hour}:{leave_by_minute:02d} AM"
    else:
        time_str = f"{leave_by_hour - 12}:{leave_by_minute:02d} PM"
    
    return time_str


def get_trip_message(trip_confidence: str, bike_likelihood: str, dock_likelihood: str, 
                     leave_by_time: Optional[str], is_morning: bool) -> str:
    """
    Generate the trip summary message based on confidence and conditions.
    """
    destination = "work" if is_morning else "home"
    
    if trip_confidence == "LOW":
        return "Consider transit/walking"
    
    if trip_confidence == "HIGH":
        return "Safe to bike"
    
    # MEDIUM cases
    if bike_likelihood == "HIGH" and dock_likelihood == "LOW":
        return f"Docks may be tight at {destination}"
    
    # MEDIUM bikes cases - check for "leave by" time
    if leave_by_time:
        return f"Safe to bike, but leave by {leave_by_time}"
    
    return "Safe to bike"


def create_prediction_panel(prediction: dict) -> Text:
    """Create the prediction display."""
    if not prediction:
        return Text("⚠️ No prediction data available", style="dim italic")
    
    result = Text()
    
    # Bike prediction
    bike_style, bike_symbol = get_likelihood_style(prediction["bike_likelihood"])
    result.append("  🚲 Get a Bike:   ", style="white")
    result.append(f"{prediction['bike_likelihood']} {bike_symbol}", style=bike_style)
    if prediction.get("bike_warning"):
        result.append(f"    ⚠️ {prediction['bike_warning']}", style="yellow italic")
    
    result.append("\n")
    
    # Dock prediction
    dock_style, dock_symbol = get_likelihood_style(prediction["dock_likelihood"])
    result.append("  🔌 Find a Dock:  ", style="white")
    result.append(f"{prediction['dock_likelihood']} {dock_symbol}", style=dock_style)
    if prediction.get("dock_warning"):
        result.append(f"    ⚠️ {prediction['dock_warning']}", style="yellow italic")
    
    return result


def create_location_panel(location_name: str, location_data: dict,
                          nearby_stations: list, prediction: dict) -> Panel:
    """Create a panel showing nearby stations for a location."""
    
    # Create prediction section at top
    pred_text = create_prediction_panel(prediction)
    pred_panel = Panel(
        pred_text,
        box=box.SIMPLE,
        padding=(0, 0),
        border_style="dim"
    )
    
    # Create the stations table
    table = Table(
        show_header=True,
        header_style="bold magenta",
        box=box.ROUNDED,
        expand=True,
        padding=(0, 1)
    )
    
    table.add_column("Station", style="cyan", no_wrap=False, width=30)
    table.add_column("Distance", justify="right", style="yellow", width=8)
    table.add_column("🚲 Bikes", justify="left", width=20)
    table.add_column("🔌 Docks", justify="left", width=20)
    
    for station in nearby_stations:
        bikes = station["bikes_available"]
        ebikes = station["ebikes_available"]
        docks = station["docks_available"]
        capacity = station["capacity"]
        
        # Station name with charging indicator
        name = station["name"]
        if station["is_charging"]:
            name = f"⚡ {name}"
        
        # Distance
        dist = format_distance(station["distance"])
        
        # Bikes column: bar + counts
        bike_text = Text()
        bike_text.append_text(get_bike_bar(bikes, ebikes, capacity, 12))
        bike_text.append(" ")
        bike_text.append(f"{bikes}", style=get_availability_style(bikes, capacity))
        if ebikes > 0:
            bike_text.append(f"+{ebikes}e", style="cyan")
        
        # Docks column: bar + count
        dock_text = Text()
        dock_text.append_text(get_dock_bar(docks, capacity, 12))
        dock_text.append(" ")
        dock_text.append(f"{docks}", style=get_availability_style(docks, capacity))
        dock_text.append(f"/{capacity}", style="dim")
        
        table.add_row(name, dist, bike_text, dock_text)
    
    # Calculate totals
    total_bikes = sum(s["bikes_available"] for s in nearby_stations)
    total_ebikes = sum(s["ebikes_available"] for s in nearby_stations)
    total_docks = sum(s["docks_available"] for s in nearby_stations)
    
    # Summary line
    summary = Text()
    summary.append(f"\n📊 Nearby Totals: ", style="bold white")
    summary.append(f"{total_bikes} bikes", style="bold blue")
    summary.append(" + ", style="dim")
    summary.append(f"{total_ebikes} e-bikes", style="bold cyan")
    summary.append(" | ", style="dim")
    summary.append(f"{total_docks} docks", style="bold green")
    
    # Combine all elements
    content = Group(pred_panel, table, Align.center(summary))
    
    return Panel(
        content,
        title=f"{location_data['emoji']} {location_name}",
        title_align="left",
        border_style="bright_blue",
        padding=(1, 2)
    )


def create_trip_summary(origin_prediction: dict, destination_prediction: dict, 
                        origin_bikes: int, is_morning: bool) -> Panel:
    """
    Create the trip summary panel that appears at the top.
    
    Args:
        origin_prediction: Prediction data for origin location (where you get bikes)
        destination_prediction: Prediction data for destination (where you dock)
        origin_bikes: Total bikes available at origin (closest 2 stations)
        is_morning: True if before noon (home->work), False if afternoon (work->home)
    """
    now = datetime.now()
    
    # Get likelihoods
    bike_likelihood = origin_prediction.get("bike_likelihood", "LOW") if origin_prediction else "LOW"
    dock_likelihood = destination_prediction.get("dock_likelihood", "LOW") if destination_prediction else "LOW"
    net_flow_bikes = origin_prediction.get("net_flow_bikes", 0) if origin_prediction else 0
    
    # Calculate trip confidence
    trip_confidence = calculate_trip_confidence(bike_likelihood, dock_likelihood)
    
    # Calculate leave by time (only if bikes trending down)
    leave_by_time = calculate_leave_by_time(
        origin_bikes, 
        net_flow_bikes,
        now.hour,
        now.minute
    )
    
    # Get the message
    message = get_trip_message(trip_confidence, bike_likelihood, dock_likelihood, 
                               leave_by_time, is_morning)
    
    # Style based on confidence
    if trip_confidence == "HIGH":
        style = "bold green"
    elif trip_confidence == "MEDIUM":
        style = "bold yellow"
    else:
        style = "bold red"
    
    # Build the text
    trip_text = Text()
    trip_text.append("Trip: ", style="bold white")
    trip_text.append(f"{trip_confidence}", style=style)
    trip_text.append(" - ", style="dim")
    trip_text.append(message, style=style)
    
    # Add direction indicator
    direction = "Home → Work" if is_morning else "Work → Home"
    direction_text = Text()
    direction_text.append(f"({direction})", style="dim italic")
    
    content = Text()
    content.append_text(trip_text)
    content.append("  ")
    content.append_text(direction_text)
    
    return Panel(
        Align.center(content),
        box=box.ROUNDED,
        border_style=style.replace("bold ", ""),
        padding=(0, 2)
    )


def create_header() -> Panel:
    """Create the header panel."""
    now = datetime.now()
    day_full = DAY_FULL_NAMES[now.weekday()]
    
    title = Text()
    title.append("🚴 ", style="bold")
    title.append("Toronto Bike Share", style="bold blue")
    title.append(" • ", style="dim")
    title.append("Live Availability + Predictions", style="bold green")
    
    subtitle = Text()
    subtitle.append(f"{day_full} {now.strftime('%Y-%m-%d %I:%M:%S %p')}", style="dim italic")
    
    header_content = Text()
    header_content.append_text(title)
    header_content.append("\n")
    header_content.append_text(subtitle)
    
    return Panel(
        Align.center(header_content),
        box=box.DOUBLE,
        border_style="bright_blue",
        padding=(0, 2)
    )


def create_legend() -> Panel:
    """Create the legend panel."""
    legend = Text()
    legend.append("█", style="blue")
    legend.append(" Regular Bikes  ", style="dim")
    legend.append("█", style="cyan")
    legend.append(" E-Bikes  ", style="dim")
    legend.append("█", style="green")
    legend.append(" Available Docks  ", style="dim")
    legend.append("░", style="dim")
    legend.append(" Empty/Used  ", style="dim")
    legend.append("⚡", style="yellow")
    legend.append(" Charging Station", style="dim")
    
    legend.append("\n")
    legend.append("Predictions: ", style="bold")
    legend.append("HIGH", style="bold green")
    legend.append("=good availability+stable trend  ", style="dim")
    legend.append("MEDIUM", style="bold yellow")
    legend.append("=okay but changing  ", style="dim")
    legend.append("LOW", style="bold red")
    legend.append("=limited availability", style="dim")
    
    return Panel(
        Align.center(legend),
        box=box.ROUNDED,
        border_style="dim",
        padding=(0, 1)
    )


def get_dashboard_data(locations: dict) -> Optional[dict]:
    """
    Fetch all data and calculate predictions for the dashboard.
    Returns a dictionary structure suitable for rendering or JSON output.
    """
    # Load predictions
    predictions = load_predictions()
    
    # Fetch live data
    try:
        stations_info, stations_status = get_station_data()
    except Exception as e:
        return {"error": f"Error fetching data: {e}"}

    # Determine trip direction based on time of day
    now = datetime.now()
    is_morning = now.hour < 12  # Before noon = home -> work
    
    # Set origin and destination keys
    # Note: Config uses "Home" and "Work" keys
    if is_morning:
        origin_name = "Home"
        destination_name = "Work"
    else:
        origin_name = "Work"
        destination_name = "Home"
    
    # Ensure we have Home and Work keys
    if "Home" not in locations or "Work" not in locations:
        return {"error": "Configuration error: Missing Home or Work location. Please run with --setup"}

    # Find nearby stations for each location and store data
    location_data = {}
    
    for loc_name, loc_data in locations.items():
        nearby = find_nearby_stations(
            loc_data["lat"], loc_data["lon"],
            stations_info, stations_status,
            NUM_NEARBY_STATIONS
        )
        
        # Get predictions for this location's stations
        prediction = get_prediction_for_stations(nearby, predictions)
        
        # Calculate total bikes at closest prediction stations
        prediction_stations = nearby[:NUM_PREDICTION_STATIONS]
        total_bikes = sum(s["bikes_available"] for s in prediction_stations)
        
        location_data[loc_name] = {
            "loc_data": loc_data,
            "nearby": nearby,
            "prediction": prediction,
            "total_bikes": total_bikes
        }
    
    # Get origin and destination data for trip summary
    origin_data = location_data[origin_name]
    destination_data = location_data[destination_name]
    
    # Calculate trip confidence
    # We need to recreate the logic from create_trip_summary here to return raw data
    
    origin_prediction = origin_data["prediction"]
    destination_prediction = destination_data["prediction"]
    origin_bikes = origin_data["total_bikes"]
    
    # Get likelihoods
    bike_likelihood = origin_prediction.get("bike_likelihood", "LOW") if origin_prediction else "LOW"
    dock_likelihood = destination_prediction.get("dock_likelihood", "LOW") if destination_prediction else "LOW"
    net_flow_bikes = origin_prediction.get("net_flow_bikes", 0) if origin_prediction else 0
    
    # Calculate trip confidence
    trip_confidence = calculate_trip_confidence(bike_likelihood, dock_likelihood)
    
    # Calculate leave by time (only if bikes trending down)
    leave_by_time = calculate_leave_by_time(
        origin_bikes, 
        net_flow_bikes,
        now.hour,
        now.minute
    )
    
    # Get the message
    message = get_trip_message(trip_confidence, bike_likelihood, dock_likelihood, 
                               leave_by_time, is_morning)
    
    # Calculate station stats
    total_stations = len([s for s in stations_status.values() if s.get("status") == "IN_SERVICE"])
    data_source = predictions.get('metadata', {}).get('data_source', 'historical data') if predictions else "unknown"

    return {
        "timestamp": now.isoformat(),
        "is_morning": is_morning,
        "direction": {
            "from": origin_name,
            "to": destination_name
        },
        "trip_summary": {
            "confidence": trip_confidence,
            "message": message,
            "leave_by": leave_by_time,
            "bike_likelihood": bike_likelihood,
            "dock_likelihood": dock_likelihood
        },
        "locations": location_data,
        "meta": {
            "total_stations": total_stations,
            "prediction_source": data_source
        }
    }


def build_dashboard_group(data: dict) -> Group:
    """
    Build the Rich renderable group for the dashboard.
    Returns a Group object that can be printed or used in Live display.
    """
    if "error" in data:
        return Group(Text(data['error'], style="red"))

    renderables = []

    # Header
    renderables.append(create_header())
    renderables.append(Text(""))  # Spacer
    
    # Trip summary
    origin_name = data["direction"]["from"]
    destination_name = data["direction"]["to"]
    
    trip_panel = create_trip_summary(
        origin_prediction=data["locations"][origin_name]["prediction"],
        destination_prediction=data["locations"][destination_name]["prediction"],
        origin_bikes=data["locations"][origin_name]["total_bikes"],
        is_morning=data["is_morning"]
    )
    renderables.append(trip_panel)
    renderables.append(Text(""))
    
    # Location panels
    # Force order: Origin then Destination
    ordered_keys = [origin_name, destination_name]
    
    for loc_name in ordered_keys:
        loc_data = data["locations"][loc_name]
        # Use address as title if available, otherwise just "Home"/"Work"
        title = loc_data["loc_data"].get("address", loc_name)
        panel = create_location_panel(title, loc_data["loc_data"], loc_data["nearby"], loc_data["prediction"])
        renderables.append(panel)
        renderables.append(Text(""))
    
    renderables.append(create_legend())
    renderables.append(Text(""))
    
    # Footer
    pred_info = f" • Predictions based on {data['meta']['prediction_source']}"
    footer = Align.center(
        Text(f"📍 Showing {NUM_NEARBY_STATIONS} nearest stations (predictions based on closest {NUM_PREDICTION_STATIONS}) • {data['meta']['total_stations']} active stations{pred_info}", style="dim")
    )
    renderables.append(footer)
    renderables.append(Text(""))
    
    return Group(*renderables)


def render_json(data: dict):
    """Render the dashboard data as JSON."""
    print(json.dumps(data, indent=2))


def render_swiftbar(data: dict):
    """
    Render the dashboard data in SwiftBar format.
    Docs: https://github.com/swiftbar/SwiftBar#plugin-output-format
    """
    if "error" in data:
        print(f"⚠️ Error | color=red")
        print("---")
        print(data['error'])
        return

    trip = data["trip_summary"]
    confidence = trip["confidence"]
    
    # 1. Menu Bar Item (The "Traffic Light")
    # Using SF Symbols: https://developer.apple.com/sf-symbols/
    symbol = "bicycle"
    color = "white"
    
    if confidence == "HIGH":
        color = "green"
    elif confidence == "MEDIUM":
        color = "yellow"
    else:
        color = "red"
        symbol = "exclamationmark.triangle"
        
    # The header line
    print(f":{symbol}: {confidence} | sfimage={symbol} color={color}")
    
    print("---")
    
    # 2. Trip Summary Section
    print(f"{trip['message']} | size=14 color={color}")
    if trip.get('leave_by'):
        print(f"Leave by: {trip['leave_by']} | size=12 color=orange")
    print("---")
    
    # 3. Location Details
    origin_name = data["direction"]["from"]
    destination_name = data["direction"]["to"]
    ordered_keys = [origin_name, destination_name]
    
    for loc_name in ordered_keys:
        loc_data = data["locations"][loc_name]
        is_origin = (loc_name == origin_name)
        role = "START" if is_origin else "END"
        emoji = loc_data["loc_data"]["emoji"]
        
        # Section Header
        print(f"{emoji} {loc_name} ({role}) | size=13 font=Menlo color=white")
        
        # Prediction
        pred = loc_data["prediction"]
        if pred:
            bike_status = f"Bikes: {pred['bike_likelihood']}"
            dock_status = f"Docks: {pred['dock_likelihood']}"
            print(f"{bike_status} • {dock_status} | size=11 color=gray")
            
            if pred.get('bike_warning'):
                print(f"⚠️ {pred['bike_warning']} | size=11 color=orange")
        
        # Station List
        for station in loc_data["nearby"]:
            bikes = station["bikes_available"]
            docks = station["docks_available"]
            name = station["name"]
            dist = format_distance(station["distance"])
            
            # Simple ASCII bar
            # We can't use complex rich bars here, so we keep it simple
            # 🚲 5  🔌 10  - Station Name (100m)
            line = f"🚲 {bikes:<2} 🔌 {docks:<2} - {name} ({dist})"
            print(f"{line} | font=Menlo size=11 trim=false")
            
        print("---")
    
    # Footer
    print("Refresh | refresh=true")
    print("Run Setup | shell=open param1='http://github.com/rehvishwanath/bikeshare-tui'")


def main():
    """Main function to run the TUI."""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Toronto Bike Share TUI")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard to configure locations")
    parser.add_argument("--once", action="store_true", help="Run once and exit (disable watch mode)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON data")
    parser.add_argument("--swiftbar", action="store_true", help="Output SwiftBar plugin format")
    args = parser.parse_args()
    
    # Run setup if requested
    if args.setup:
        locations = run_setup_wizard()
        return
    else:
        # Load config or fall back to default
        locations = load_config()
        if not locations:
            # Fallback to defaults
            locations = LOCATIONS
            # Remap to Home/Work keys for consistency if using defaults
            # (The defaults use address as key, but wizard uses "Home"/"Work")
            if "215 Fort York Blvd" in locations:
                locations = {
                    "Home": locations["215 Fort York Blvd"],
                    "Work": locations["155 Wellington St (RBC Centre)"]
                }
    
    # Initial data fetch
    # Only show spinner if running in interactive mode
    is_interactive = not (args.json or args.swiftbar)
    
    if is_interactive:
        with console.status("[bold blue]Loading dashboard data...", spinner="dots"):
            data = get_dashboard_data(locations)
    else:
        data = get_dashboard_data(locations)
    
    if not data:
        return

    # Render based on mode
    if args.json:
        render_json(data)
    elif args.swiftbar:
        render_swiftbar(data)
    elif args.once:
        console.print(build_dashboard_group(data))
    else:
        # Watch Mode (Default)
        # Use Live to update the screen
        try:
            with Live(build_dashboard_group(data), console=console, screen=True, refresh_per_second=4) as live:
                while True:
                    time.sleep(60)  # Refresh every 60 seconds
                    data = get_dashboard_data(locations)
                    if data:
                        live.update(build_dashboard_group(data))
        except KeyboardInterrupt:
            pass  # Exit cleanly on Ctrl+C


if __name__ == "__main__":
    main()
