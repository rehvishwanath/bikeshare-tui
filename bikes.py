#!/usr/bin/env python3
"""
Toronto Bike Share TUI with Predictions
A beautiful terminal interface showing available bikes and docks near specified locations,
with historical pattern-based predictions for likelihood of finding bikes/docks.
"""

import urllib.request
import json
import math
import os
from datetime import datetime
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.align import Align

# API endpoints
STATION_INFO_URL = "https://tor.publicbikesystem.net/ube/gbfs/v1/en/station_information"
STATION_STATUS_URL = "https://tor.publicbikesystem.net/ube/gbfs/v1/en/station_status"

# Path to prediction data (relative to script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PREDICTIONS_FILE = os.path.join(SCRIPT_DIR, "data", "station_patterns.json")

# Target locations (approximate coordinates)
LOCATIONS = {
    "215 Fort York Blvd": {
        "lat": 43.6395,
        "lon": -79.3960,
        "emoji": "🏠"
    },
    "155 Wellington St (RBC Centre)": {
        "lat": 43.6472,
        "lon": -79.3815,
        "emoji": "🏢"
    }
}

# How many nearby stations to show
NUM_NEARBY_STATIONS = 5

# Day name mapping
DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_FULL_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

console = Console()


def load_predictions() -> dict:
    """Load prediction patterns from JSON file."""
    if not os.path.exists(PREDICTIONS_FILE):
        return None
    with open(PREDICTIONS_FILE, 'r') as f:
        return json.load(f)


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
    
    for station in nearby_stations:
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
    
    # Dock likelihood
    if dock_pct >= 40 and total_net_flow_docks >= -2:
        dock_likelihood = "HIGH"
    elif dock_pct >= 25 or (dock_pct >= 15 and total_net_flow_docks > 0):
        dock_likelihood = "MEDIUM"
    else:
        dock_likelihood = "LOW"
    
    # Generate depletion warning messages
    bike_warning = None
    dock_warning = None
    
    if bike_depletion_warnings:
        # Find earliest depletion
        earliest = min(bike_depletion_warnings, key=lambda x: x["hour"])
        bike_warning = f"Often runs low by {earliest['hour']}:00 on {day_full}s"
    
    # For docks, invert the logic - stations filling up means bikes arriving
    if total_net_flow_bikes > 5:  # Lots of bikes arriving = docks filling
        # Find when docks typically run out
        for station in nearby_stations:
            station_id = station["id"]
            if station_id in patterns:
                # Look ahead for when net flow becomes very positive (docks filling)
                pattern = patterns[station_id]
                for future_hour in range(hour + 1, min(hour + 5, 24)):
                    future_net = pattern.get("net_flow", {}).get(day_name, {}).get(str(future_hour), 0)
                    if future_net > 8:  # Heavy inflow
                        dock_warning = f"Fills up around {future_hour}:00 on {day_full}s"
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
    table.add_column("🚲 Bikes", justify="center", width=20)
    table.add_column("🔌 Docks", justify="center", width=20)
    
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
    subtitle.append(f"{day_full} {now.strftime('%Y-%m-%d %H:%M:%S')}", style="dim italic")
    
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


def main():
    """Main function to run the TUI."""
    
    # Load predictions
    predictions = None
    with console.status("[bold blue]Loading prediction data...", spinner="dots"):
        predictions = load_predictions()
    
    with console.status("[bold blue]Fetching live bike share data...", spinner="dots"):
        try:
            stations_info, stations_status = get_station_data()
        except Exception as e:
            console.print(f"[bold red]Error fetching data:[/] {e}")
            return
    
    # Find nearby stations for each location
    location_panels = []
    for loc_name, loc_data in LOCATIONS.items():
        nearby = find_nearby_stations(
            loc_data["lat"], loc_data["lon"],
            stations_info, stations_status,
            NUM_NEARBY_STATIONS
        )
        
        # Get predictions for this location's stations
        prediction = get_prediction_for_stations(nearby, predictions)
        
        panel = create_location_panel(loc_name, loc_data, nearby, prediction)
        location_panels.append(panel)
    
    # Print the TUI
    console.print()
    console.print(create_header())
    console.print()
    
    for panel in location_panels:
        console.print(panel)
        console.print()
    
    console.print(create_legend())
    console.print()
    
    # Station count info
    total_stations = len([s for s in stations_status.values() if s.get("status") == "IN_SERVICE"])
    pred_info = ""
    if predictions:
        pred_info = f" • Predictions based on {predictions.get('metadata', {}).get('data_source', 'historical data')}"
    console.print(
        Align.center(
            Text(f"📍 Showing {NUM_NEARBY_STATIONS} nearest stations per location • {total_stations} active stations{pred_info}", style="dim")
        )
    )
    console.print()


if __name__ == "__main__":
    main()
