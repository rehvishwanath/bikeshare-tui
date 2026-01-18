# Toronto Bike Share TUI 🚲

> **Stop tapping. Start riding.**

A zero-latency, CLI-based dashboard for Toronto Bike Share commuters. Designed to solve the "death by a thousand cuts" friction of using the official mobile app for daily commutes.

![Demo](https://via.placeholder.com/800x400?text=Screenshot+Coming+Soon)

## The Problem
The official mobile app is great for tourists but painful for daily commuters.
- **Too many clicks:** 8-12 interactions just to check if you can get a bike.
- **Snapshot only:** Tells you there are 5 bikes now, but not that they usually disappear in 10 minutes.
- **No widgets:** You have to open the app, wait for the map, zoom in, and tap a pin.

## The Solution
`bikes` is a terminal command that gives you:
- **Instant Availability:** Real-time counts for your home and work locations.
- **Predictive Intelligence:** Uses historical data (5.3 million trips) to tell you if bikes are filling up or emptying out.
- **Velocity Warnings:** *"⚠️ Often runs low by 8:45am"*
- **Granular Data:** Separates E-bikes from Classic bikes instantly.

## Installation

### Prerequisites
- Python 3.8+
- Terminal with UTF-8 support (iTerm2, Terminal.app, etc.)

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/bikeshare-tui.git
   cd bikeshare-tui
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run it:
   ```bash
   python3 bikes.py
   ```

### Make it a global command

To run `bikes` from anywhere:

```bash
chmod +x bikes.py
ln -s $(pwd)/bikes.py /usr/local/bin/bikes
# OR add an alias to your shell profile
alias bikes="python3 $(pwd)/bikes.py"
```

## How It Works

### 1. Real-Time Data
Fetches live JSON feeds from the GBFS (General Bikeshare Feed Specification) API:
- `station_information.json` (Location, capacity)
- `station_status.json` (Current bikes/docks)

### 2. Predictive Engine
We processed **9 months of historical ridership data (Jan-Sep 2024)** containing **5.3 million trips**.
- We calculated the **Net Flow** (Arrivals - Departures) for every station, for every hour of the week.
- This creates a "velocity" vector: Is this station gaining or losing bikes right now?

### 3. Trend-Adjusted Predictions
The "High/Medium/Low" likelihood isn't just a guess. It combines:
- **Current State:** How many bikes are there right now?
- **Historical Velocity:** How fast do they usually leave at this hour?

| Likelihood | Logic |
|------------|-------|
| **HIGH**   | Station has bikes AND historical trend is stable/increasing. |
| **MEDIUM** | Station has bikes BUT historically empties fast at this time. |
| **LOW**    | Station is empty OR critically low and trending downwards. |

## Customization

Open `bikes.py` and edit the `LOCATIONS` dictionary to add your own favorite spots:

```python
LOCATIONS = {
    "Home": {
        "lat": 43.6395,
        "lon": -79.3960,
        "emoji": "🏠"
    },
    "Office": {
        "lat": 43.6472,
        "lon": -79.3815,
        "emoji": "🏢"
    }
}
```

## License
MIT License. Data provided by Toronto Open Data.
