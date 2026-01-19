# FAQ and Key Decisions Made

## Velocity & Depletion Warnings

### Q: Why did I see "Often runs low by 4:00" at 155 Wellington but not at 215 Fort York?
The warnings are **dynamic and data-driven**, not hardcoded to specific locations like "Work" or "Home".
- **155 Wellington:** The historical data showed that one of the nearby stations has a high risk of emptying out between 2:00 AM and 5:00 AM on Sundays.
- **215 Fort York:** The stations nearby did not meet the specific threshold for risk at that time (Severity > 15 within the next 4 hours).

### Q: What triggers these warnings?
There are two specific types of warnings based on historical patterns:

| Warning Type | Message | Trigger Condition |
| :--- | :--- | :--- |
| **Get a Bike** | *"Often runs low by {Hour}:00..."* | A station nearby has a historical **Depletion Risk** within the **next 4 hours** with a **Severity Score > 15**. |
| **Find a Dock** | *"Fills up around {Hour}:00..."* | The entire area is gaining >5 bikes/hr (net flow) **AND** a specific nearby station is gaining >8 bikes/hr. |

### Q: What does "Depletion Risk" actually mean?
It is **not** a real-time measurement. It is a calculated pattern based on 9 months of historical data (Jan–Sep 2024).
The system calculates the **Net Flow** (Arrivals - Departures) for every hour. The **Depletion Hour** is the specific hour of the day when a station's bike count historically hits its lowest point (maximum cumulative outflow).

### Q: What is the "Severity Score"?
The Severity Score represents the **Total Net Loss** of bikes for that specific hour on that day of the week, summed across the entire 9-month dataset.
- **Severity > 15:** Triggers a warning.
- **Meaning:** "Over the last 9 months, this station has collectively lost at least 15 more bikes than it gained by this specific hour."
- **Scale:** A score of 15 is a mild risk (approx. 0.5 bikes/week net loss). A score of 400+ indicates a station that almost certainly runs empty.

### Q: Why does it look at the "Next 4 Hours"?
This is a User Experience (UX) decision.
- **Actionability:** A warning that a station empties in 7 hours is noise. A warning that it empties in 2 hours is critical.
- **Safety Prioritization:** If a station has a depletion risk at 2:00 PM and a *worse* risk at 5:00 PM, the system warns about **2:00 PM**. It prioritizes the *earliest* moment you might become stranded.

---

## Key Engineering Decisions

### 1. Hyper-Local Predictions (Implemented Jan 18, 2026)
**Problem:**
Previously, the prediction logic averaged the data from all **5** nearest stations.
For locations like "155 Wellington St" (RBC Centre), this was problematic because Wellington St is long. Averaging a station 5 blocks away with the one at the front door diluted the accuracy of the warning. Use cases usually involve walking to the absolute closest station, not the 5th closest.

**Decision:**
We separated the "Visual List" from the "Prediction Logic".
- **Visuals:** Still show the **5** nearest stations so the user has fallback options.
- **Predictions:** Only calculate "High/Medium/Low" and "Warnings" based on the **closest 2** stations.

**Implementation:**
- Added `NUM_PREDICTION_STATIONS = 2` constant in `bikes.py`.
- Updated `get_prediction_for_stations` to slice the station list (`nearby_stations[:NUM_PREDICTION_STATIONS]`) before processing risks.
- Updated the UI footer to explicitly state: *"Showing 5 nearest stations (predictions based on closest 2)"*.

### 2. Trip Summary Feature (Implemented Jan 19, 2026)

**Problem:**
The app showed detailed bike and dock information for two locations, but users had to mentally synthesize this to answer: "Should I bike today?" A commuter glancing at their terminal wants an instant answer, not a data analysis exercise.

**Decision:**
Added a "Trip Summary" panel at the very top of the output that provides a single, glanceable confidence level with an actionable message.

**Key Design Choices:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Combination method** | Weighted average (60% bikes, 40% docks) + gating rule | Bikes are more critical; can't start trip without one. Docks matter less because you can ride to a nearby station. |
| **Gating rule** | LOW bikes = LOW trip, regardless of docks | Abundant docks are meaningless if you can't get a bike. |
| **"Leave by" calculation** | Dynamic based on current bikes ÷ flow rate | Responds to actual conditions, not just historical patterns. |
| **Direction detection** | Time-based (before noon = home→work) | Simplest approach that works for the common case. |
| **Display location** | Very top, before station panels | Executive summary comes first - answer the question before showing details. |

**Implementation:**
- Added `calculate_trip_confidence()` function with weighted average logic.
- Added `calculate_leave_by_time()` for dynamic time calculation.
- Added `create_trip_summary()` to render the panel.
- Updated `main()` to determine direction and display summary first.

**See also:** [Trip Summary Feature Documentation](./Trip_Summary_Feature.md) for complete design rationale.

### 3. Setup Wizard & Geocoding (Implemented Jan 19, 2026)

**Problem:**
Hardcoded coordinates for "Home" and "Work" were error-prone. A test user found the hardcoded "215 Fort York Blvd" coordinates were 800m off, showing the wrong stations.

**Decision:**
Implemented an interactive **Setup Wizard** (`bikes --setup`) that allows users to enter their own addresses.

**Key Design Choices:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Geocoding Provider** | **OpenStreetMap (Nominatim)** | Chosen over Google Maps to avoid forcing users to generate API keys. It's free and open. |
| **Verification** | **"Trust but Fallback"** | The wizard finds the address, shows a minimalist confirmation (Street + Number), and saves it. No complex "verify by station" interrogation. |
| **Storage** | `~/.bikes_config.json` | Settings persist locally in the user's home directory. |
| **Backward Compatibility** | **Demo Mode** | If no config exists, the app still runs using the default locations (now corrected), so new users can see it work immediately. |

**See also:** [Setup Wizard Feature Documentation](./Setup_Wizard_Feature.md).

---

## Setup Wizard: Detailed Q&A

### Q: Why OpenStreetMap instead of Google Maps?

Google Maps requires an API key. To get one, a user would need to:
1. Create a Google Cloud account
2. Add a credit card
3. Generate an API key
4. Paste it into a config file

This is a massive barrier for a simple CLI tool. OpenStreetMap's Nominatim API is free and requires no authentication.

### Q: What was the "800-meter error"?

The original hardcoded coordinates for "215 Fort York Blvd" were manually estimated and placed the user 800 meters **east** of their actual building (on the wrong side of Bathurst St). This caused the app to show completely different stations than the ones visible from the user's window.

This discovery drove the requirement for geocoding-based setup rather than manual coordinate entry.

### Q: Why not show autocomplete suggestions as the user types?

CLI (Command Line Interface) limitations. Unlike a web app with JavaScript, a standard terminal input doesn't support real-time dropdowns. Implementing this would require complex terminal UI libraries and would be brittle across different shells (bash, zsh, Windows cmd).

### Q: Why ask for confirmation instead of just trusting the geocode result?

Even good geocoding can occasionally pick the wrong building or the center of a large complex. The confirmation step catches the 5% of cases where the API picks wrong, without adding friction to the 95% that work correctly.

### Q: Why include postal code in the confirmation but not city/province?

The user is already in Toronto using a Toronto bike share app. City and province are implied. But postal code is:
- Specific to the building
- Something users remember about their address
- A second verification layer (if the postal code looks wrong, the address is wrong)

### Q: What happens if I don't run --setup?

The app falls back to hardcoded default locations (Demo Mode). This ensures:
- New users can try the app immediately
- The app never crashes due to missing config
- Users see real data for a sample Toronto commute

### Q: Where is my configuration stored?

In a hidden JSON file in your home directory: `~/.bikes_config.json`

You can view or edit it manually if needed:
```bash
cat ~/.bikes_config.json
```

---

## Trip Summary Feature: Detailed Q&A

### Q: Why does docks weigh less than bikes (40% vs 60%)?

Once you have a bike, you're mobile. If your destination dock is full, you can ride 2 minutes to a nearby station. It's inconvenient, not a failure.

But if there are no bikes at your origin, you can't start the trip at all. You're stuck walking or waiting for transit. This is why bikes are weighted higher **and** have a gating rule.

### Q: What is the "gating rule"?

If bike likelihood at your origin is LOW, the trip confidence is automatically LOW - regardless of how many docks are available at your destination.

The formula:
```python
if bike_likelihood == "LOW":
    return "LOW"  # Gating rule: can't start without bikes
else:
    # Calculate weighted average
    trip_score = (bike_score * 0.6) + (dock_score * 0.4)
```

### Q: How was the 60/40 split determined?

This was a reasoned estimate based on the asymmetry of failure modes:

| Scenario | Impact | Recovery |
|----------|--------|----------|
| No bikes at origin | Can't start trip | Walk to transit, wait, change plans |
| No docks at destination | Can't end trip at first choice | Ride 2-3 min to next station |

Docks having a 40% weight means they still matter (LOW docks pulls the score down), but not enough to override good bike availability.

### Q: Why show "leave by" only within 1 hour?

If the "leave by" time is 2+ hours away, there's no urgency. Saying "leave by 10:30 AM" at 7:00 AM is noise, not actionable information.

The 1-hour window was chosen because:
- It's immediate enough to affect your current decision
- It's far enough out to give you time to react
- It matches typical morning routines (check at 7:30 AM, leave by 8:30 AM)

### Q: Why is the "leave by" buffer 30 minutes?

The buffer accounts for:
- Time to get ready (5-10 min)
- Walking to the station (5-10 min)
- Margin for error in our estimate (10-15 min)

30 minutes is a reasonable buffer for most urban commutes. If you live further from a station, you'd naturally leave earlier anyway.

### Q: What if I check at 11 AM for an afternoon trip home?

The app would incorrectly show "Home → Work" because it's still before noon.

**Why this is acceptable:**
- It's a rare edge case (most people check right before commuting)
- The detailed panels below still show both locations
- Adding a toggle adds complexity for minimal benefit

This trade-off prioritizes simplicity for the 95% case.

### Q: How does "leave by" get calculated?

**Formula:**
```
hours_until_floor = (current_bikes - 5) / bikes_lost_per_hour
depletion_time = current_time + hours_until_floor
leave_by = depletion_time - 30 minutes
```

**Example:**
- 11 bikes now, losing 3/hour
- Hits floor of 5 in: (11-5) / 3 = 2 hours
- At 7:00 AM → floor at 9:00 AM
- Leave by: 9:00 AM - 30 min = **8:30 AM**

### Q: Why only show "leave by" based on origin bikes, not destination docks?

Only bikes at the origin determine whether you can start the trip. Docks at the destination matter, but:
- By the time you arrive, dock availability may have changed
- You can always ride to a nearby station if needed
- The "leave soon" message is specifically about grabbing a bike

We considered checking both trends, but decided it added complexity without clarity. "Leave by 8:30 AM to get a bike" is specific and actionable. "Leave by 8:30 AM because of bikes or maybe docks" is confusing.

### Q: What are all the possible trip messages?

| Trip Level | Condition | Message |
|------------|-----------|---------|
| HIGH | Any | "Safe to bike" |
| MEDIUM | HIGH bikes, LOW docks | "Docks may be tight at [work/home]" |
| MEDIUM | Bikes trending down, ≤1hr | "Safe to bike, but leave by [time]" |
| MEDIUM | Otherwise | "Safe to bike" |
| LOW | Any | "Consider transit/walking" |

### Q: What are the threshold scores?

| Level | Score Range | How to Achieve |
|-------|-------------|----------------|
| HIGH | ≥ 2.5 | HIGH/HIGH (3.0) or HIGH/MEDIUM (2.6) |
| MEDIUM | 1.8 to 2.5 | MEDIUM/MEDIUM (2.0), MEDIUM/HIGH (2.4), HIGH/LOW (2.2) |
| LOW | < 1.8 | MEDIUM/LOW (1.6) or gating rule triggers |
