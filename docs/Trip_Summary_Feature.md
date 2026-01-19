# Trip Summary Feature: Design and Implementation

This document captures the complete design process for the Trip Summary feature, including all options considered, decisions made, and the reasoning behind each choice. This feature was designed through an iterative conversation exploring various approaches before arriving at the final implementation.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Design Goals](#design-goals)
3. [Definition of Trip Success](#definition-of-trip-success)
4. [Combining Bike and Dock Likelihoods](#combining-bike-and-dock-likelihoods)
5. [Trip Confidence Messages](#trip-confidence-messages)
6. [The "Leave By" Time](#the-leave-by-time)
7. [Morning vs Evening Detection](#morning-vs-evening-detection)
8. [UI/UX Decisions](#uiux-decisions)
9. [Complete Implementation Reference](#complete-implementation-reference)
10. [Summary of All Decisions](#summary-of-all-decisions)

---

## Problem Statement

The original app showed detailed information about bike and dock availability at two locations (home and work), but required the user to mentally synthesize this information to answer the fundamental question:

> **"Should I bike today, or should I take transit/walk?"**

A commuter waking up in the morning doesn't want to analyze two panels of station data. They want a **single, glanceable answer** that tells them:

1. Whether biking is viable right now
2. If they need to hurry
3. If they should consider alternatives

### The User Story

> As a Toronto bike share commuter, I want to glance at my terminal and within one second know if I should bike to work today, so I can make a quick transportation decision without analyzing multiple data points.

---

## Design Goals

| Goal | Description |
|------|-------------|
| **Instant clarity** | Answer "should I bike?" in under 1 second of looking at the screen |
| **Actionable** | If action is needed (leave soon, consider transit), say so explicitly |
| **Non-redundant** | Don't repeat information already shown in the detailed panels below |
| **Directionally aware** | Understand that morning = home→work, evening = work→home |
| **Evidence-based** | Build on existing prediction model, not introduce new unvalidated logic |

---

## Definition of Trip Success

### What Makes a Trip Successful?

**Decision:** A successful bike share trip requires two things:
1. **Finding an available bike at the origin** (where you start)
2. **Finding an available dock at the destination** (where you end)

### Options Considered

| Factor | Considered? | Decision |
|--------|-------------|----------|
| Bike at origin | Yes | **Required** - can't start without a bike |
| Dock at destination | Yes | **Required** - can't end without a dock |
| Weather | Discussed | **Deferred** - could add later via weather API, but doesn't change the core model |
| Travel time | No | Out of scope - user knows their route |

### Weather: A Future Enhancement

Weather was discussed as a potential factor:
- Could pull from a weather API to warn about rain or snow
- For winter months, could reason about whether roads have been cleared after heavy snow
- **Decision:** Keep weather as a future enhancement. It's an overlay on top of the core bike/dock logic, not a replacement for it.

---

## Combining Bike and Dock Likelihoods

### The Core Question

Given two independent likelihoods:
- **Bike likelihood at origin:** HIGH / MEDIUM / LOW
- **Dock likelihood at destination:** HIGH / MEDIUM / LOW

How do we combine them into a single **Trip Confidence**?

### Options Considered

#### Option A: Weakest Link
Trip confidence = the lower of the two.
- If bikes are HIGH but docks are LOW, trip is LOW.

**Pros:** Simple, conservative.
**Cons:** Treats bikes and docks as equally important, which isn't true.

#### Option B: Weighted Average
Weight bikes more heavily than docks (e.g., 60/40 split).

**Pros:** Reflects reality that bikes are more critical.
**Cons:** Requires choosing weights and thresholds.

#### Option C: Matrix Approach
Define explicit combinations in a lookup table.

**Pros:** Full control over every combination.
**Cons:** Harder to maintain, may have inconsistencies.

### Decision: Weighted Average with Gating Rule

We chose **Option B (Weighted Average)** with an additional **gating rule**.

**Rationale for weighting docks less (40%):**
- Once you have a bike, you're mobile
- If your destination dock is full, you can ride to a nearby station
- This adds minor inconvenience, not trip failure

**Rationale for the gating rule:**
- If there are no bikes at your origin, you can't start the trip at all
- Abundant docks at your destination are meaningless if you can't get a bike
- Therefore: **LOW bikes = LOW trip, regardless of dock score**

### The Formula

**Step 1: Convert likelihoods to numeric scores**
```python
HIGH = 3
MEDIUM = 2
LOW = 1
```

**Step 2: Check the gating rule**
```python
if bike_likelihood == "LOW":
    return "LOW"  # Can't start trip without bikes
```

**Step 3: Calculate weighted average**
```python
BIKE_WEIGHT = 0.6
DOCK_WEIGHT = 0.4

trip_score = (bike_score * BIKE_WEIGHT) + (dock_score * DOCK_WEIGHT)
```

**Step 4: Convert score back to category**
```python
if trip_score >= 2.5:
    return "HIGH"
elif trip_score >= 1.8:
    return "MEDIUM"
else:
    return "LOW"
```

### Why These Thresholds?

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| HIGH threshold | 2.5 | Requires strong performance on both metrics. Only achievable with HIGH/HIGH or HIGH/MEDIUM. |
| MEDIUM threshold | 1.8 | Allows for one weaker metric if the other compensates. MEDIUM/MEDIUM (2.0) passes. |

### Complete Combination Matrix

| Bikes | Docks | Calculation | Score | Trip Confidence |
|-------|-------|-------------|-------|-----------------|
| LOW | * | Gating rule | N/A | **LOW** |
| MEDIUM | LOW | (2×0.6) + (1×0.4) | 1.6 | **LOW** |
| MEDIUM | MEDIUM | (2×0.6) + (2×0.4) | 2.0 | **MEDIUM** |
| MEDIUM | HIGH | (2×0.6) + (3×0.4) | 2.4 | **MEDIUM** |
| HIGH | LOW | (3×0.6) + (1×0.4) | 2.2 | **MEDIUM** |
| HIGH | MEDIUM | (3×0.6) + (2×0.4) | 2.6 | **HIGH** |
| HIGH | HIGH | (3×0.6) + (3×0.4) | 3.0 | **HIGH** |

---

## Trip Confidence Messages

### The Question

What message should accompany each trip confidence level?

### Options Considered

#### Option A: Just the confidence level
```
Trip Confidence: HIGH
```

#### Option B: Confidence + recommendation
```
Trip Confidence: HIGH - Safe to bike
Trip Confidence: LOW - Consider transit
```

#### Option C: Confidence + brief reason
```
Trip Confidence: MEDIUM (docks may be tight at work)
```

### Decision: Option B with Contextual Reasoning

We chose a hybrid approach:
- Always show the confidence level + a recommendation
- For MEDIUM, vary the message based on *why* it's medium

### Message Logic

| Trip | Condition | Message |
|------|-----------|---------|
| **HIGH** | Any | "Safe to bike" |
| **LOW** | Any | "Consider transit/walking" |
| **MEDIUM** | HIGH bikes, LOW docks | "Docks may be tight at [destination]" |
| **MEDIUM** | Bikes trending down, within 1 hour | "Safe to bike, but leave by [time]" |
| **MEDIUM** | All other cases | "Safe to bike" |

### Why "Docks may be tight" Only for HIGH/LOW?

When bikes are HIGH but docks are LOW:
- You'll definitely get a bike (HIGH)
- But you might struggle to dock (LOW)
- The concern is specifically about docks, so we call it out

When bikes are MEDIUM:
- The concern is about bikes, not docks
- We use the "leave by" message if bikes are trending down
- Otherwise, it's still safe enough to bike

### Destination Label: Dynamic Based on Direction

The message says "at work" or "at home" depending on the time of day:
- **Morning (before noon):** destination = work
- **Evening (noon and after):** destination = home

---

## The "Leave By" Time

### The Question

When bike availability is MEDIUM and trending down, how do we calculate when the user should leave?

### Options Considered

#### Option A: Based on Depletion Hour (historical pattern)
Use the pre-calculated hour when the station historically runs low.

**Pros:** Already have this data.
**Cons:** Static - doesn't account for current conditions.

#### Option B: Based on Current Count + Net Flow (dynamic)
Calculate how long until bikes drop below the floor based on current availability and flow rate.

**Pros:** Responsive to actual conditions.
**Cons:** More calculation.

#### Option C: Whichever is Sooner
Take the earlier of historical depletion or projected depletion.

**Pros:** Most conservative.
**Cons:** May be overly cautious.

### Decision: Option B (Dynamic Calculation)

We chose the dynamic approach because:
- It responds to what's actually happening right now
- If there are more bikes than usual, the "leave by" time adjusts accordingly
- If there are fewer bikes than usual, it warns earlier

### The Calculation

**Variables:**
- `current_bikes`: Total bikes at the closest 2 stations
- `net_flow_bikes`: How many bikes the area is gaining/losing per hour (from historical data)
- `ABSOLUTE_BIKE_FLOOR = 5`: The minimum bike count we consider acceptable
- `LEAVE_BY_BUFFER_MINUTES = 30`: Buffer time before hitting the floor

**Formula:**
```python
# Step 1: How many bikes above the floor?
bikes_above_floor = current_bikes - ABSOLUTE_BIKE_FLOOR

# Step 2: How long until we hit the floor?
loss_rate = abs(net_flow_bikes)  # bikes lost per hour
hours_until_floor = bikes_above_floor / loss_rate

# Step 3: When should you leave?
depletion_time = current_time + hours_until_floor
leave_by = depletion_time - 30 minutes
```

### Worked Example

**Scenario:**
- Current time: 7:00 AM
- Current bikes: 11
- Net flow: -3 bikes/hour (losing 3 bikes per hour)
- Floor: 5 bikes
- Buffer: 30 minutes

**Calculation:**
```
Step 1: Bikes above floor
  11 - 5 = 6 bikes of "cushion"

Step 2: Time until floor
  6 bikes ÷ 3 bikes/hour = 2 hours
  → Hits floor at 9:00 AM

Step 3: Leave by time
  9:00 AM - 30 min buffer = 8:30 AM
```

**Result:** "Safe to bike, but leave by 8:30 AM"

### Edge Cases

#### What if "Leave By" is in the Past?

**Scenario:** User checks at 9:00 AM, but calculated leave_by was 8:30 AM.

**Decision:** Don't show the "leave by" message.

**Rationale:** If the time has passed, the current bike count should already reflect the depleted state. The trip confidence will naturally be lower. Showing a stale time adds confusion.

#### What if "Leave By" is Far in the Future?

**Scenario:** Leave by calculates to 2+ hours from now.

**Decision:** Only show "leave by" if it's within 1 hour.

**Rationale:** If you have 2+ hours, there's no urgency. Saying "leave by 10:30 AM" at 7:00 AM is noise, not information.

#### What if Net Flow is Positive or Zero?

**Decision:** Don't show "leave by" if bikes aren't depleting.

**Rationale:** If bikes are arriving or stable, there's no impending shortage to warn about.

### Display Rules Summary

| Condition | Show "Leave By"? |
|-----------|------------------|
| Net flow negative AND leave_by within 1 hour | Yes |
| Net flow negative AND leave_by > 1 hour away | No (just say "Safe to bike") |
| Net flow positive or zero | No |
| Leave by time already passed | No |

---

## Morning vs Evening Detection

### The Question

How does the app know which direction the commute is going?

### Options Considered

#### Option A: Time-based Auto-detect
- Before 12 PM → morning commute (home → work)
- 12 PM and after → evening commute (work → home)

#### Option B: Always Show Both Directions
Display two trip summaries, one for each direction.

#### Option C: User Toggle/Flag
Add a command-line flag like `bikes --to-work` or `bikes --to-home`.

### Decision: Option A (Time-based Auto-detect)

**Rationale:**
- Simplest approach - no user input required
- Correct for the vast majority of use cases
- A commuter checks `bikes` right before leaving, not hours in advance

**Trade-off acknowledged:**
If you check at 11 AM for an afternoon trip home, it would show the wrong direction. This is acceptable because:
- It's a rare edge case
- The detailed panels below still show both locations
- The feature is optimized for the common case (checking right before commuting)

### Implementation

```python
now = datetime.now()
is_morning = now.hour < 12  # Before noon

if is_morning:
    origin = HOME_LOCATION
    destination = WORK_LOCATION
else:
    origin = WORK_LOCATION
    destination = HOME_LOCATION
```

---

## UI/UX Decisions

### Placement

**Question:** Where should the trip summary appear?

**Options:**
- A) Very top, before everything else
- B) Between header and station details

**Decision:** Option A - Very top.

**Rationale:** This is the "executive summary" - the answer to the user's main question. It should be the first thing they see, before diving into details.

### Visual Output

```
╭──────────────────────────────────────────────────────────────────────────────╮
│                   Trip: HIGH - Safe to bike  (Work → Home)                   │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### Styling

**Question:** How should it be styled?

**Options:**
- A) Match existing color scheme (green/yellow/red)
- B) Add emphasis with a box
- C) Both (colored text in a box)

**Decision:** Option A - Colored text matching existing scheme.

**Rationale:** 
- Keeps it clean and consistent with the rest of the app
- A heavy box might be visually overwhelming
- The color already provides sufficient emphasis

### Color Mapping

| Confidence | Color | Style |
|------------|-------|-------|
| HIGH | Green | `bold green` |
| MEDIUM | Yellow | `bold yellow` |
| LOW | Red | `bold red` |

---

## Complete Implementation Reference

### New Constants Added

```python
# Trip confidence calculation
TRIP_BIKE_WEIGHT = 0.6      # Bikes are more important (gating factor)
TRIP_DOCK_WEIGHT = 0.4      # Docks matter less (can ride to nearby station)
TRIP_HIGH_THRESHOLD = 2.5   # Score needed for HIGH confidence
TRIP_MEDIUM_THRESHOLD = 1.8 # Score needed for MEDIUM confidence

# "Leave by" calculation
LEAVE_BY_BUFFER_MINUTES = 30  # Buffer before hitting the floor
LEAVE_BY_MAX_HOURS = 1        # Only show if within this many hours

# Location keys
HOME_LOCATION = "215 Fort York Blvd"
WORK_LOCATION = "155 Wellington St (RBC Centre)"
```

### New Functions Added

#### `likelihood_to_score(likelihood: str) -> int`
Converts HIGH/MEDIUM/LOW to 3/2/1.

#### `score_to_likelihood(score: float) -> str`
Converts numeric score back to likelihood using thresholds.

#### `calculate_trip_confidence(bike_likelihood: str, dock_likelihood: str) -> str`
Applies the gating rule and weighted average to determine trip confidence.

#### `calculate_leave_by_time(...) -> Optional[str]`
Calculates the dynamic "leave by" time based on current conditions.

#### `get_trip_message(...) -> str`
Generates the appropriate message based on confidence and conditions.

#### `create_trip_summary(...) -> Panel`
Creates the Rich panel for display at the top of the output.

### Integration Points

The `main()` function was updated to:
1. Determine trip direction based on time of day
2. Identify origin and destination locations
3. Calculate trip confidence from origin bikes + destination docks
4. Generate and display the trip summary before location panels

---

## Summary of All Decisions

| Decision Point | Options Considered | Final Choice | Rationale |
|----------------|-------------------|--------------|-----------|
| Trip success definition | Bikes only, docks only, both | **Both required** | Need bike to start, dock to end |
| Combination method | Weakest link, weighted average, matrix | **Weighted average + gating** | Bikes more critical, but docks still matter |
| Weight split | Various ratios | **60% bikes, 40% docks** | Bikes are gating factor; docks have workarounds |
| Gating rule | With or without | **With gating** | LOW bikes = trip failure, regardless of docks |
| HIGH threshold | Various values | **2.5** | Ensures at least one HIGH component |
| MEDIUM threshold | Various values | **1.8** | Allows MEDIUM/MEDIUM to pass |
| Message style | Level only, with recommendation, with reason | **Recommendation + contextual reason** | Actionable and specific |
| "Leave by" calculation | Historical, dynamic, combined | **Dynamic** | Responds to current conditions |
| "Leave by" buffer | Various durations | **30 minutes** | Time to get ready and walk to station |
| "Leave by" visibility | Always, conditional | **Only within 1 hour** | Avoid noise for non-urgent situations |
| Which trend for "leave soon" | Origin bikes, destination docks, both | **Origin bikes only** | Bikes determine if you can start the trip |
| Direction detection | Time-based, toggle, both | **Time-based auto-detect** | Simplest, works for common case |
| Cutoff time | Various hours | **12 PM (noon)** | Natural midday split |
| UI placement | Top, between sections | **Very top** | Executive summary comes first |
| Styling | Box, colors, both | **Colors matching existing scheme** | Clean, consistent |

---

## Design Philosophy

This feature embodies several key principles:

### 1. Answer the Real Question First
The user's actual question is "should I bike?" Everything else is supporting detail. Lead with the answer.

### 2. Progressive Disclosure
- **Level 1:** Trip confidence (1 second to understand)
- **Level 2:** Detailed panels for each location (if user wants more)
- **Level 3:** Source documentation (for the curious)

### 3. Fail Toward Caution
When in doubt, the system errs conservative:
- Gating rule prevents false confidence when bikes are low
- "Leave by" includes a 30-minute buffer
- MEDIUM is the fallback when conditions are ambiguous

### 4. Leverage Existing Work
The trip summary builds entirely on the existing prediction model:
- Uses the same bike/dock likelihoods
- Uses the same net flow data
- Uses the same absolute floor concept

No new data sources or prediction logic was needed - just a new way of combining existing signals.
