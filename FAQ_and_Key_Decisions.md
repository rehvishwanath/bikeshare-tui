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
