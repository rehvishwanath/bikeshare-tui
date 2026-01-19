# Prediction Model Design: Why Simple Statistics Work

This document explains the design decisions behind our bike availability prediction system, the evidence that supports these decisions, and why we chose a straightforward statistical approach over more complex machine learning methods.

---

## Key Terms and Definitions

Before diving into the model, here are the key terms used throughout this document:

| Term | Definition |
|------|------------|
| **Departures** | Bikes leaving a station (someone unlocks and rides away). |
| **Arrivals** | Bikes returning to a station (someone docks a bike). |
| **Net Flow** | `Arrivals - Departures` for a given time period. Positive = gaining bikes. Negative = losing bikes. |
| **Depletion Hour** | The hour of the day when a station historically hits its lowest bike count. |
| **Severity Score** | The cumulative net bike loss at the Depletion Hour, summed across all weeks in the dataset. Higher = more consistent/severe depletion. |
| **bike_pct** | Current bike availability as a percentage of capacity. `(bikes_available / total_capacity) * 100`. |
| **Absolute Floor** | A minimum bike count below which we consider availability risky, regardless of percentage. |
| **Hyper-Local** | Predictions based only on the closest 2 stations, not a wider average. |

### Hourly Granularity vs. Weekly Averaging

A common point of confusion: when we say "net flow of -2.2 bikes/week," this does **not** mean the station loses 2.2 bikes over an entire week.

**What it actually means:**
- The data is measured at **hourly granularity** (e.g., "Sunday 11 AM to 12 PM").
- The "per week" refers to **averaging across 39 weeks** of historical data to smooth out noise.

**Example:**
```
Station 7000 - Sunday 11 AM:
  Departures: 6.0 (average across 39 Sundays, during the 11 AM hour)
  Arrivals: 3.9 (average across 39 Sundays, during the 11 AM hour)
  Net Flow: -2.2 (this station loses ~2 bikes during the 11 AM hour on Sundays)
```

So "-2.2 net flow" means: **"Every Sunday, specifically between 11 AM and 12 PM, this station typically loses about 2 bikes."**

| Dimension | Granularity |
|-----------|-------------|
| Time of day | Per hour (0-23) |
| Day of week | Per day (Mon-Sun) |
| Data smoothing | Averaged across 39 weeks |

---

## The Core Insight: Cyclical Behavior

Bike share usage is fundamentally **cyclical and predictable**. Unlike domains where user behavior is chaotic or driven by unpredictable external factors, urban commuting follows deeply ingrained patterns tied to:

1. **Work schedules** (9-5 jobs, shift work)
2. **Day of week** (weekdays vs. weekends)
3. **Time of day** (rush hours, lunch breaks, evenings)
4. **Seasons** (in countries with multiple seasons, ridership follows predictable seasonal curves—higher in spring/summer, lower in winter)

These patterns repeat week after week with high consistency.

### Evidence from Historical Data

Our dataset covers **9 months** (January–September 2024) of Toronto Bike Share ridership data, representing approximately **39 weeks** of observations across **870 stations**.

When we aggregate departures and arrivals by `(station, day_of_week, hour)`, clear patterns emerge:

| Station Type | Weekday 8 AM | Weekday 6 PM | Weekend Noon |
|--------------|--------------|--------------|--------------|
| Residential (e.g., Fort York) | High departures | High arrivals | Moderate both |
| Commercial (e.g., Wellington/Bay) | High arrivals | High departures | Low activity |

This inverse relationship between residential and commercial stations is consistent across the dataset. It reflects the simple reality: people leave home in the morning and return in the evening.

**Sample Data Point (Station 7151, Mondays):**
```
Hour  Departures/wk  Arrivals/wk  Net Flow
 7       1.2            0.5         -0.7  (losing bikes)
 8       2.1            0.4         -1.7  (losing bikes)
17       1.9            2.8         +0.9  (gaining bikes)
18       2.1            2.5         +0.4  (gaining bikes)
```

The pattern is unmistakable: bikes flow *out* of residential areas in the morning and flow *back* in the evening.

---

## Why Not Machine Learning?

Machine learning excels when:
- Patterns are non-obvious or require feature engineering
- Relationships between variables are complex and non-linear
- You have millions of data points and need to generalize across unseen scenarios

None of these conditions apply here.

### The Case Against ML for This Problem

| Factor | Reality |
|--------|---------|
| **Pattern Complexity** | Patterns are simple and linear. "Tuesday 8 AM" behaves like every other "Tuesday 8 AM." |
| **Feature Engineering** | The only meaningful features are `station_id`, `day_of_week`, and `hour`. No complex interactions. |
| **Generalization Need** | We don't need to predict for unseen stations or times. We have historical data for every combination. |
| **Interpretability** | A lookup table is 100% explainable. "This station loses 3 bikes/hour on Friday mornings" is immediately understandable. |
| **Maintenance Burden** | ML models require retraining, hyperparameter tuning, and monitoring for drift. A statistical model just needs a data refresh. |

### What ML Would Add (and Why It's Unnecessary)

An ML model could theoretically account for:
- **Weather:** Rain reduces ridership. But weather is unpredictable days in advance, so it doesn't help a "what should I expect today" prediction.
- **Events:** Concerts, sports games cause spikes. But these are rare and localized; the baseline pattern still dominates.
- **Holidays:** Yes, holidays differ. But they're a small fraction of days, and a simple "is_holiday" flag would suffice.

The marginal accuracy gain from ML does not justify the complexity cost for this use case.

---

## The Target User: Urban Commuters

This app is designed for **daily commuters** who use bike share as part of their regular routine.

### Commuter Behavior Characteristics

1. **Repetitive Routes:** Same origin (home) and destination (work) every day.
2. **Consistent Timing:** Leave for work within a 30-minute window most days.
3. **Low Tolerance for Uncertainty:** A commuter needs to *know* they can get a bike, not *hope*.
4. **Planning Horizon:** Decisions are made minutes before departure, not hours.

### What Commuters Need

| Need | How We Address It |
|------|-------------------|
| "Will there be a bike when I leave?" | Show current availability + historical trend for this exact time slot. |
| "Will it run out soon?" | Warn if the station typically depletes within the next 4 hours. |
| "What's my backup?" | Show the 5 nearest stations so they can pivot quickly. |

A commuter doesn't need a probability distribution. They need a simple signal: **HIGH** (you're fine), **MEDIUM** (it might get tight), or **LOW** (find an alternative).

---

## The Model: How It Works

### Step 1: Aggregate Historical Data

For every `(station, day, hour)` tuple, we calculate:
- **Departures per week:** Average number of bikes leaving.
- **Arrivals per week:** Average number of bikes arriving.
- **Net Flow:** `Arrivals - Departures`. Positive = gaining bikes. Negative = losing bikes.

### Step 2: Calculate Cumulative Depletion

For each station and day, we simulate the flow of bikes hour-by-hour:
```
cumulative_flow = 0
for hour in 0..23:
    cumulative_flow += net_flow[hour]
    if cumulative_flow < min_cumulative:
        min_cumulative = cumulative_flow
        depletion_hour = hour
```

The **Depletion Hour** is when the station historically hits its lowest point. The **Severity** is the magnitude of that low point (total bikes lost).

### Step 3: Severity Threshold

The **Severity Score** is not a percentage or a probability—it is a raw count of cumulative bike loss over the historical dataset.

**What it represents:**
- A Severity of **50** means: "Over 39 weeks of data, by this hour on this day, this station had cumulatively lost 50 more bikes than it gained."
- Divided by weeks, that's ~1.3 bikes/week net loss—a modest but consistent drain.

**Why we use a threshold of 15:**

| Severity | Interpretation | Action |
|----------|----------------|--------|
| < 15 | Negligible risk. Random fluctuation, not a pattern. | No warning. |
| 15–50 | Mild risk. Station trends toward empty but usually recovers. | Show warning if imminent. |
| 50–200 | Moderate risk. Station reliably drains at this time. | Show warning. |
| > 200 | High risk. Station is a major exporter of bikes (e.g., near transit hub). | Show warning with high confidence. |

The threshold of **15** filters out noise. With 39 weeks of data, a severity below 15 means the station loses less than 0.4 bikes/week on average—statistically insignificant and likely due to variance rather than a true pattern.

**How it's incorporated:**
```python
if severity > 15 and 0 < (depletion_hour - current_hour) <= 4:
    show_warning("Often runs low by {depletion_hour} on {day}s")
```

Both conditions must be true:
1. **Severity > 15:** The pattern is real, not noise.
2. **Within 4 hours:** The risk is imminent and actionable.

### Step 4: Real-Time Prediction

When the app runs, it:
1. Fetches **live availability** from the Toronto Bike Share API.
2. Looks up the **historical net flow** for the current `(station, day, hour)`.
3. Combines them using the Likelihood Thresholds (see below).

---

## Likelihood Thresholds: The Decision Logic

The app displays one of three signals: **HIGH**, **MEDIUM**, or **LOW**. Here's exactly how that decision is made.

### The Thresholds

```python
# HIGH: Good availability AND stable/improving trend
if bike_pct >= 40 and net_flow >= -2:
    likelihood = "HIGH"

# MEDIUM: Okay availability OR low-but-improving
elif bike_pct >= 25 or (bike_pct >= 15 and net_flow > 0):
    likelihood = "MEDIUM"

# LOW: Everything else
else:
    likelihood = "LOW"
```

### What Each Variable Means

| Variable | Source | Meaning |
|----------|--------|---------|
| `bike_pct` | Live API | Current bikes as % of capacity (e.g., 18 bikes / 74 capacity = 24.3%) |
| `net_flow` | Historical JSON | How many bikes this station gains/loses during this hour on this day (e.g., -2.2 = losing ~2 bikes/hour) |

### Threshold Breakdown

| Level | Condition | Interpretation |
|-------|-----------|----------------|
| **HIGH** | `bike_pct >= 40%` AND `net_flow >= -2` | "Plenty of bikes right now, and the station isn't draining fast." |
| **MEDIUM** | `bike_pct >= 25%` OR (`bike_pct >= 15%` AND `net_flow > 0`) | "Availability is okay" OR "It's low but bikes are arriving." |
| **LOW** | Everything else | "Low availability AND the trend is negative. Risky." |

### Worked Example: 215 Fort York Blvd, Sunday 11 AM

**Step 1: Gather Current Data (from Live API)**

| Station (Closest 2) | Bikes | Capacity |
|---------------------|-------|----------|
| Fort York Blvd / Capreol Ct | 14 | 47 |
| Dan Leckie Way / Fort York Blvd | 4 | 27 |
| **Total** | **18** | **74** |

```
bike_pct = 18 / 74 = 24.3%
```

**Step 2: Look Up Historical Net Flow (from station_patterns.json)**

| Station | Net Flow (Sunday 11 AM) |
|---------|-------------------------|
| Fort York Blvd / Capreol Ct | -2.2 bikes/hour |
| Dan Leckie Way / Fort York Blvd | -0.8 bikes/hour |
| **Total** | **-3.0 bikes/hour** |

**Step 3: Apply the Logic**

```
Check HIGH: 24.3% >= 40%? NO. → Not HIGH.
Check MEDIUM: 24.3% >= 25%? NO.
             24.3% >= 15% AND -3.0 > 0? NO (flow is negative). → Not MEDIUM.
Default: LOW
```

**Result:** The app shows **LOW** because:
1. Current availability (24.3%) is below the 25% threshold.
2. The trend is negative (-3.0 bikes/hour), so it's not improving.

### The Problem with Pure Percentages

In the example above, 18 bikes is probably *enough* for a single commuter. But the percentage-based logic sees "24.3% < 25%" and flags it as concerning.

This is why we introduced the **Absolute Floor** (see next section).

---

## The Absolute Floor: Minimum Bike Count

### The Problem

Percentage-based thresholds can be misleading:
- 5 bikes at a 10-dock station = 50% → HIGH
- 18 bikes at a 74-dock station = 24% → LOW

But 18 bikes is objectively *more* than 5 bikes. A commuter only needs **one working bike**.

### Reasoning Through the Floor

**What does a commuter actually need?**
- 1 working bike.

**What could go wrong?**

| Risk | Impact | Mitigation |
|------|--------|------------|
| Some bikes are damaged (flat tire, broken seat, etc.) | ~10% of docked bikes may be unusable | Need a buffer |
| Someone else takes a bike while you're walking to the station | Reduces available count | Need a buffer |
| API data is slightly stale (30-60 seconds) | Minor discrepancy | Minimal impact |

**Estimating Damage Rate:**
Based on general bike share industry data, approximately **5-10%** of docked bikes have minor issues that make them unrideable. We assume 10% as a conservative estimate.

**Working Backwards:**

| Available Bikes | After 10% Damaged | After 1-2 Others Take | Left for You |
|-----------------|-------------------|----------------------|--------------|
| 3 | 2-3 | 1-2 | **0-1** (risky) |
| 5 | 4-5 | 2-3 | **2-3** (okay) |
| 8 | 7 | 5 | **5** (comfortable) |
| 15 | 13-14 | 11-12 | **11-12** (very safe) |

### The Decision: Floor of 5

We set an **absolute floor of 5 bikes**:
- If there are at least 5 bikes across the closest 2 stations, the likelihood is **at minimum MEDIUM** (never LOW).
- Below 5 bikes, percentage-based logic applies normally.

**Rationale:**
- 5 bikes → ~4-5 usable after damage → enough for a commuter even if 1-2 are taken.
- Low enough to not mask genuine scarcity (4 bikes can still be LOW).
- High enough to prevent false alarms (18 bikes should never be LOW).

**Implementation:**
```python
# After calculating likelihood from percentages...
if total_bikes >= 5 and bike_likelihood == "LOW":
    bike_likelihood = "MEDIUM"  # Override: enough absolute bikes
```

### How This Changes the Example

With the absolute floor applied to the Fort York example:
- `total_bikes = 18` (well above floor of 5)
- Original likelihood: LOW
- **After floor applied: MEDIUM**

This better reflects reality: 18 bikes is enough, even if the percentage looks low.

### What About Docks? Bikes vs Docks Comparison

The absolute floor applies to **both** bikes and docks, but the reasoning differs slightly.

| Factor | Bikes | Docks |
|--------|-------|-------|
| **Damage rate** | ~10% (flat tires, broken seats, stuck pedals) | ~1-2% (payment terminal issues, stuck locking mechanisms) |
| **Race condition** | Others grabbing bikes while you walk | Others docking while you arrive |
| **Failure consequence** | Walk or wait | **Overtime fees** ($4/30min after grace period) |
| **Recovery options** | Walk to next station, wait for rebalancing | Must dock *somewhere* or pay fees |

**Why docks have lower damage rate:**
- Docks are simpler mechanical systems (just a locking slot + sensor)
- No moving parts that wear out from riding
- Weather damage is less impactful (no exposed chains, tires, seats)

**Why dock failure is worse:**
- With bikes: you haven't started your trip yet. Worst case = walk or wait.
- With docks: you're *mid-trip*. If you can't dock, the meter keeps running.
- Toronto Bike Share charges $4 per 30 minutes after the 30-minute grace period.
- Riding to the next station takes time, potentially pushing you past the grace period.

**The Decision: Same Floor of 5 for Docks**

Despite the lower damage rate, we keep the floor at 5 for docks because:

1. **Consequence severity:** Overtime fees are a worse outcome than walking to get a bike
2. **Simplicity:** One floor value is easier to reason about and maintain
3. **Conservative approach:** For something with worse failure consequences, we'd rather be more conservative, not less

**Implementation:**
```python
# Same floor logic for docks
if total_docks >= 5 and dock_likelihood == "LOW":
    dock_likelihood = "MEDIUM"  # Override: enough absolute docks
```

---

## Step 5: Warnings

If the Depletion Hour for a nearby station falls within the next 4 hours, and the Severity exceeds a threshold (>15 cumulative bikes lost), the app displays a warning:

> "Often runs low by 4 PM on Fridays"

This gives the commuter advance notice to leave earlier or pick a different station.

---

## Step 6: Trip Confidence (Combined Prediction)

While individual bike and dock likelihoods are useful, commuters need a single answer: **"Should I bike today?"**

The Trip Confidence combines origin bike likelihood and destination dock likelihood into one signal.

### The Problem with Separate Predictions

A commuter sees:
- Home: Bikes = MEDIUM, Docks = HIGH
- Work: Bikes = HIGH, Docks = LOW

What does this mean for their morning commute? They need to mentally:
1. Realize morning = home → work
2. Extract "bikes at home" (MEDIUM) and "docks at work" (LOW)
3. Synthesize these into a decision

The Trip Confidence does this automatically.

### Combining Likelihoods: Weighted Average with Gating

**Why not just take the minimum?**
Taking the lower of (bikes, docks) treats them as equally important. But they're not:
- **Bikes at origin:** Gating factor. No bikes = no trip.
- **Docks at destination:** Important but recoverable. No docks = ride to next station.

**The Formula:**

```python
# Convert to scores
SCORES = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# Gating rule: LOW bikes = LOW trip
if bike_likelihood == "LOW":
    return "LOW"

# Weighted average
BIKE_WEIGHT = 0.6
DOCK_WEIGHT = 0.4

trip_score = (bike_score * BIKE_WEIGHT) + (dock_score * DOCK_WEIGHT)

# Convert back
if trip_score >= 2.5:
    return "HIGH"
elif trip_score >= 1.8:
    return "MEDIUM"
else:
    return "LOW"
```

### Threshold Rationale

| Threshold | Value | Effect |
|-----------|-------|--------|
| HIGH | ≥ 2.5 | Requires HIGH/HIGH (3.0) or HIGH/MEDIUM (2.6) |
| MEDIUM | ≥ 1.8 | Allows MEDIUM/MEDIUM (2.0), HIGH/LOW (2.2), MEDIUM/HIGH (2.4) |
| LOW | < 1.8 | MEDIUM/LOW (1.6) or gating rule |

### Complete Combination Matrix

| Origin Bikes | Dest. Docks | Calculation | Score | Trip |
|--------------|-------------|-------------|-------|------|
| LOW | * | Gating rule | — | **LOW** |
| MEDIUM | LOW | 1.2 + 0.4 | 1.6 | **LOW** |
| MEDIUM | MEDIUM | 1.2 + 0.8 | 2.0 | **MEDIUM** |
| MEDIUM | HIGH | 1.2 + 1.2 | 2.4 | **MEDIUM** |
| HIGH | LOW | 1.8 + 0.4 | 2.2 | **MEDIUM** |
| HIGH | MEDIUM | 1.8 + 0.8 | 2.6 | **HIGH** |
| HIGH | HIGH | 1.8 + 1.2 | 3.0 | **HIGH** |

### Dynamic "Leave By" Time

When trip confidence is MEDIUM due to trending-down bikes, the app calculates a "leave by" time:

```python
bikes_above_floor = current_bikes - ABSOLUTE_FLOOR  # e.g., 11 - 5 = 6
hours_until_floor = bikes_above_floor / loss_rate   # e.g., 6 / 3 = 2 hours
leave_by = current_time + hours_until_floor - 30_minutes_buffer
```

This is only shown if:
- Net flow is negative (bikes are depleting)
- Leave by time is within 1 hour (imminent urgency)
- Leave by time hasn't already passed

**For detailed design documentation, see:** [Trip Summary Feature](./Trip_Summary_Feature.md)

---

## Design Principles

### 1. Transparency Over Black Boxes
Every prediction can be traced back to a simple average. There is no hidden model, no unexplainable weights. If a user asks "why did you say LOW?", we can show them the exact historical data.

### 2. Hyper-Local Accuracy
We restrict predictions to the **2 closest stations** rather than averaging across a wider area. A station 300m away filling up doesn't help you if the one at your door is empty.

### 3. Actionable Warnings
Warnings are only shown if:
- The risk is **imminent** (within 4 hours).
- The risk is **significant** (Severity > 15).

We avoid noise. A warning that a station *might* be slightly less full at midnight is not useful.

### 4. Graceful Degradation
If historical data is missing for a station, the app still works—it just shows live availability without trend context. The user is never blocked.

---

## Future Considerations

While the current model is intentionally simple, we've identified areas for potential enhancement:

| Enhancement | Rationale | Complexity |
|-------------|-----------|------------|
| **Seasonal Adjustments** | Winter ridership differs from summer. Weight recent weeks more heavily. | Low |
| **Holiday Detection** | Flag statutory holidays and weekends-before-holidays. | Low |
| **Weather Integration** | If rain is forecast, suppress "HIGH" predictions. | Medium |
| **Real-Time Velocity** | Compare current availability to 15-minutes-ago to detect sudden drains. | Medium |

These would be additive improvements, not replacements for the core statistical model.

---

## Summary

We chose simple statistics because:

1. **The problem is cyclical.** Bike share usage repeats predictably by day and hour.
2. **The data supports it.** 9 months of history shows consistent patterns station-by-station.
3. **The user needs simplicity.** Commuters want a quick signal, not a probability curve.
4. **Complexity has costs.** ML models require ongoing maintenance with minimal accuracy gains for this domain.

The result is a prediction system that is fast, interpretable, and directly tied to observable reality.
