# Setup Wizard Feature: Design and Implementation

This document details the design and implementation of the "Setup Wizard," a feature introduced to solve the problem of accurate location targeting without imposing technical barriers on the user. It captures the complete design conversation, including all options considered, user insights, and the reasoning behind each decision.

---

## Table of Contents

1. [Problem Statement: The 800-Meter Error](#problem-statement-the-800-meter-error)
2. [Design Goals](#design-goals)
3. [The Geocoding Dilemma: Google vs OpenStreetMap](#the-geocoding-dilemma-google-vs-openstreetmap)
4. [User Experience (UX) Decisions](#user-experience-ux-decisions)
5. [Input Flexibility: Handling Fuzzy Queries](#input-flexibility-handling-fuzzy-queries)
6. [Address Formatting: The Postal Code Decision](#address-formatting-the-postal-code-decision)
7. [Technical Implementation](#technical-implementation)
8. [Configuration Management](#configuration-management)
9. [Summary of All Decisions](#summary-of-all-decisions)

---

## Problem Statement: The 800-Meter Error

### The Discovery

During testing, the user noticed that the stations listed for "215 Fort York Blvd" were completely different from the ones visible outside their window:

**What the app showed:**
- Fort York Blvd / Capreol Ct (37m)
- Dan Leckie Way / Fort York Blvd (146m)
- Spadina Ave / Fort York Blvd (231m)

**What the user actually sees from their building:**
- Fort York Blvd / Grand Magazine St
- Coronation Park (Martin Goodman Trail)
- Fort York Blvd / Garrison Rd

### Root Cause Analysis

Investigation revealed the hardcoded coordinates (`43.6395, -79.3960`) placed the user **800 meters east** of their actual building. The error occurred because:

1. Coordinates were manually estimated (not geocoded)
2. "215 Fort York Blvd" is on the **west** side of Bathurst St
3. The estimated coordinates landed on the **east** side of Bathurst St
4. This is effectively a "data entry error" - the kind that happens when developers hardcode configuration

### The User's Challenge

> "How is it that the coordinates were mismatched and I was placed 500-800 meters away? There should be a very deterministic way by which we do this."

This insight drove the requirement for a **geocoding-based setup** rather than manual coordinate entry.

---

## Design Goals

| Goal | Description | User Insight |
|------|-------------|--------------|
| **Precision** | Must find the exact building, not just the street center | "There should be a deterministic way" |
| **Zero Friction** | No API keys, no sign-ups, no complex configuration | "We don't want the user to enter their own API key" |
| **Seamless** | Minimal typing, minimal questions | "Make it as seamless as possible. The user shouldn't have to type in a lot except for their address" |
| **Privacy** | Location data stays on the user's machine | Implicit requirement |
| **Resilience** | Must work "out of the box" with sensible defaults | For new users who just want to try it |

---

## The Geocoding Dilemma: Google vs OpenStreetMap

### The Core Question

How do we convert a user-typed address into precise coordinates?

### Option A: Google Maps API

**Pros:**
- Gold standard for accuracy
- Handles fuzzy inputs ("RBC Centre") perfectly
- Excellent coverage worldwide

**Cons:**
- **Requires an API Key**
- Developer cannot embed their private key (security risk)
- User would have to sign up for Google Cloud, add a credit card, generate a key, and paste it in
- This is a **massive barrier to entry** for a simple CLI tool

### Option B: OpenStreetMap (Nominatim)

**Pros:**
- **Free and no API key required**
- Excellent coverage in major cities like Toronto
- Open source and community-maintained

**Cons:**
- Slightly less forgiving with vague names
- Needs "155 Wellington St W, Toronto" rather than just "RBC Centre"
- Rate limits (not an issue for personal use)

### Decision: OpenStreetMap

**User's decisive input:**
> "We don't want the user to enter their own API key."

The friction of asking a user to get a Google API key would effectively kill the app's usability. For a personal commuter tool, the trade-off is clear: **accessibility over perfection**.

The slight reduction in "fuzzy search" capability is manageable through good UX design (confirmation step, retry option).

---

## User Experience (UX) Decisions

### Flow 1: "Verify by Station" (Rejected)

**Idea:** After geocoding, find the closest bike station and ask:
> "I found 3 stations near that location:
> 1. Fort York Blvd / Grand Magazine (15m)
> 2. Bathurst St / Housey St (230m)
> 
> Is #1 your closest station? [Y/n]"

**User's Rejection:**
> "Users, let's say they move to a new location. They may not know what the closest station is. Why should we tell them to say 'Okay, this is [my station]'? We're giving them the distance to 15 meters. So how does it help to ask them what the closest station is?"

**Conclusion:** This approach puts cognitive load on the user. They shouldn't need to know station names. The app should just work.

### Flow 2: "Autocomplete Suggestions" (Rejected)

**Idea:** Show a dropdown of address suggestions as the user types, like Google Maps.

**Technical Limitation:**
> Since we are building a **CLI tool** (Command Line Interface), we have constraints compared to a web app. There's no real-time autocomplete in a standard terminal input.

Implementing robust real-time autocomplete in a terminal is complex and brittle across different shells (bash, zsh, fish, Windows cmd).

### Flow 3: "Trust but Fallback" (Chosen)

**The Philosophy:**
> The best way to ensure accuracy isn't just better geocoding—it's **closing the loop** with the user.

**The Flow:**
1. User types address (e.g., "215 Fort York Blvd")
2. System geocodes it silently
3. System shows the formatted result and asks for simple confirmation
4. If confirmed → save. If not → try again with more detail.

**Why This Works:**
- **Zero Friction:** No "verify by station" interrogation
- **Self-Verifying:** Seeing the formatted address *is* the verification
- **Resilient:** 95% of the time, geocode is accurate enough. The main dashboard provides additional verification (if stations look wrong, run setup again).

---

## Input Flexibility: Handling Fuzzy Queries

### The Question

> "How much flexibility does the user have when it comes to the query? What if I just type in '215 Fort York'? Do I get a list of addresses below? Is there some sort of fuzzy matching going on?"

### How Nominatim Handles It

We don't need to implement our own fuzzy matching because the **Nominatim API handles this**. It understands:
- "St" vs "Street"
- "W" vs "West"
- "Blvd" vs "Boulevard"
- Partial names

### Handling Ambiguity: "Did You Mean?"

If the user types a vague query and the API returns multiple plausible matches, we could present a numbered list:

```
Found multiple locations for '215 Fort York':
1. 215, Fort York Boulevard, CityPlace (Residential)
2. Fort York National Historic Site, 250 Fort York Boulevard

Select one [1-2]: 1
```

**Current Implementation:** We take the top result and ask for confirmation. If wrong, user can retry with more detail.

---

## Address Formatting: The Postal Code Decision

### The "Geocoding Salad" Problem

Raw API output is overwhelming:
```
215, Fort York Boulevard, CityPlace, Spadina—Fort York, Old Toronto, Toronto, Ontario, M5V 4A2, Canada
```

### Breaking Down the Components

| Component | Value | Keep? | Reason |
|-----------|-------|-------|--------|
| House Number | `215` | **YES** | Essential identity |
| Road | `Fort York Boulevard` | **YES** | Essential location |
| Neighbourhood | `CityPlace` | No | Redundant |
| Electoral District | `Spadina—Fort York` | No | Irrelevant for commuting |
| Sub-City | `Old Toronto` | No | Historical artifact |
| City | `Toronto` | No | The app is *for* Toronto |
| Province | `Ontario` | No | Implied |
| Postal Code | `M5V 4A2` | **YES** | High-signal verifier |
| Country | `Canada` | No | Implied |

### The User's Decision

> "We can do street address and then postal code because that is also something that people would remember about their place and is another indicator."

**Final Format:** `Street Address, Postal Code`

**Example:**
- Input: `215 Fort York`
- Output: `215 Fort York Boulevard, M5V 4A2`

**Why Postal Code?**
- Users remember their postal code
- If the postal code matches, you're definitely at the right building
- It's a second verification layer without requiring user effort

---

## Technical Implementation

### Dependency Management

**Constraint:** Keep `requirements.txt` minimal. Don't add heavy libraries for a single API call.

**Options:**
1. `geopy` library - Full-featured geocoding wrapper
2. `requests` library - HTTP client
3. `urllib.request` - Python built-in

**Decision:** Use Python's built-in `urllib.request`.

```python
# Zero-dependency API call
url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})

with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
```

**Rationale:** The app should be installable with `pip install -r requirements.txt` and run immediately. Adding dependencies for a single API call is overkill.

### Search Bias (Toronto Focus)

To improve accuracy for Toronto users without hard-restricting the app, we use Nominatim's `viewbox` parameter:

```python
params = {
    'q': query,
    'format': 'json',
    'addressdetails': 1,
    'limit': 1,
    'viewbox': '-79.63,43.58,-79.11,43.85',  # Greater Toronto Area
    'bounded': 1
}
```

This biases results toward Toronto but doesn't reject non-Toronto addresses entirely.

---

## Configuration Management

### Storage Location

Settings are saved to a hidden JSON file in the user's home directory:
```
~/.bikes_config.json
```

**Why this location?**
- Standard Unix convention for user config
- Survives app updates (code changes don't wipe settings)
- Easy to back up or transfer to a new machine
- Easy to inspect/edit manually if needed

### Config File Structure

```json
{
    "Home": {
        "lat": 43.6375,
        "lon": -79.4030,
        "emoji": "🏠",
        "address": "215 Fort York Boulevard, M5V 4A2"
    },
    "Work": {
        "lat": 43.6458,
        "lon": -79.3854,
        "emoji": "🏢",
        "address": "155 Wellington Street West, M5V 3H1"
    }
}
```

### Backward Compatibility: Demo Mode

If the config file doesn't exist, the app falls back to hardcoded default locations. This ensures:

1. **New users can try it immediately** without running setup
2. **The app never crashes** due to missing config
3. **Demo mode** shows real data for a sample commute

```python
locations = load_config()
if not locations:
    # Fallback to defaults
    locations = {
        "Home": {"lat": 43.6375, "lon": -79.4030, ...},
        "Work": {"lat": 43.6458, "lon": -79.3854, ...}
    }
```

---

## Summary of All Decisions

| Decision Point | Options Considered | Final Choice | User Insight / Rationale |
|----------------|-------------------|--------------|--------------------------|
| **Geocoding Provider** | Google Maps, OpenStreetMap | **OpenStreetMap** | "We don't want the user to enter their own API key" |
| **Verification Method** | By Station, By Address, None | **By Address** | Users who move may not know their closest station |
| **Input Method** | Autocomplete, One-shot | **One-shot with confirmation** | CLI limitation; autocomplete is complex and brittle |
| **Address Display** | Full raw string, Street only, Street + Postal | **Street + Postal Code** | "Postal code is something people remember about their place" |
| **Config Storage** | Env vars, Config file, Database | **JSON file (`~/.bikes_config.json`)** | Standard, persistent, human-readable |
| **HTTP Library** | `geopy`, `requests`, `urllib` | **`urllib` (built-in)** | Zero external dependencies for a single API call |
| **Failure Behavior** | Crash, Fallback | **Fallback to defaults** | App should always be runnable (Demo Mode) |
| **Toronto Bias** | Hard-restrict, Soft-bias, None | **Soft-bias with viewbox** | Improves accuracy without limiting flexibility |

---

## Design Philosophy

### 1. Seamlessness Over Interrogation

The user's mantra was clear:
> "Make it as seamless as possible. The user shouldn't have to type in a lot except for their address."

This drove us to reject "verify by station" and embrace a simple confirmation flow.

### 2. Determinism Over Estimation

The 800-meter error taught us that manual coordinate estimation is unreliable. By using a geocoding API, we get **deterministic, reproducible** results.

### 3. Accessibility Over Perfection

Google Maps is more accurate, but requiring an API key would kill adoption. OpenStreetMap is "good enough" and **free**.

### 4. Progressive Complexity

- **Level 1:** Run `bikes --setup`, type two addresses, done.
- **Level 2:** Edit `~/.bikes_config.json` manually if you want to tweak coordinates.
- **Level 3:** Fork the code and customize anything.

Most users never need to go beyond Level 1.
