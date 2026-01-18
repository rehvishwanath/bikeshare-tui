# Prediction Model Design: Why Simple Statistics Work

This document explains the design decisions behind our bike availability prediction system, the evidence that supports these decisions, and why we chose a straightforward statistical approach over more complex machine learning methods.

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
3. Combines them:
   - **HIGH:** Current availability is good (>40%) AND trend is stable or positive.
   - **MEDIUM:** Current availability is okay (>25%) OR improving.
   - **LOW:** Current availability is poor OR trend shows rapid depletion.

### Step 5: Warnings

If the Depletion Hour for a nearby station falls within the next 4 hours, and the Severity exceeds a threshold (>15 cumulative bikes lost), the app displays a warning:

> "Often runs low by 4 PM on Fridays"

This gives the commuter advance notice to leave earlier or pick a different station.

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
