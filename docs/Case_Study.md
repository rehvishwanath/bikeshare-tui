# Terminal Velocity: Solving "Death by a Thousand Cuts" in the Toronto Bike Share Experience

## 1. Problem Statement
The official Toronto Bike Share mobile app (PBSC) is a generalist tool designed for tourists and casual riders, not power users or daily commuters. For a regular commuter with a fixed route (e.g., Fort York to the Financial District), the app introduces significant friction. It treats every session as a new exploration rather than a recurring habit.

The core problem is **latency of information**. In the time-critical window of a morning commute, a rider needs binary answers immediately: *Can I get a bike?* and *Can I dock it when I arrive?* The current app requires a high cognitive load—navigating maps, filtering pins, and interpreting snapshots of data—to answer these simple questions.

## 2. Objective
To build a zero-latency, "at-a-glance" dashboard for the terminal (TUI) that provides:
1.  **Immediate Availability:** Real-time bike/dock counts for specific, pre-defined locations.
2.  **Granularity:** Distinguishing between Classic Bikes, E-Bikes, and Docks without extra clicks.
3.  **Predictive Context:** Using historical data to gauge the *velocity* of availability (is the station filling up or emptying out?), rather than just a static snapshot.

## 3. Target Demographic
**The "Power Commuter."**
This user lives in the terminal. They are likely a developer or data-adjacent professional. They have a predictable route (Home ↔ Office). They value efficiency over UI polish. They do not need a map; they know where the station is. They need to know if the station is *viable*.

## 4. Understanding the Current State (The Audit)
We conducted a user journey audit of the current Toronto Bike Share app (PBSC) for a commute from **215 Fort York Blvd** to **155 Wellington St (RBC Centre)**.

### The "No Widget" Void & Search Friction
To get any information, the user *must* engage fully with the application. There are no shortcuts.

<table>
  <tr>
    <td width="50%" align="center">
      <img src="../assets/clean_no_widget.png" alt="No Widget"><br>
      <b>1. The Blank Canvas</b><br>
      No lock screen or home screen widgets mean every interaction starts from zero.
    </td>
    <td width="50%" align="center">
      <img src="../assets/clean_search_friction.png" alt="Search Friction"><br>
      <b>2. Search Ambiguity</b><br>
      Searching "Wellington" returns addresses, not just stations. Which one is correct?
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="../assets/clean_map_clutter.png" alt="Map Clutter"><br>
      <b>3. The "Tap-to-Reveal"</b><br>
      The map hides critical details like distance to dock behind a tap and search view.
    </td>
    <td width="50%" align="center">
      <img src="../assets/clean_hidden_details.png" alt="Hidden Details"><br>
      <b>4. Buried Details</b><br>
      Granular info like E-bike counts is hidden deep in sub-menus with no visual indicator for bikes vs ebikes.
    </td>
  </tr>
</table>

## 5. User Journey Comparison

### Journey A: The Official App (Current State)
*Goal: Check availability for morning commute.*

1.  **Unlock Phone.** (No widget available).
2.  **Locate & Tap App.**
3.  **Wait for Load.** Map renders. GPS centers.
4.  **Locate Origin.** Zoom/Pan to Fort York.
5.  **Visual Scan.** See a "10" bubble.
6.  **Tap Pin.** Reveal details: "0 E-bikes, 10 Classic, 8 Docks."
7.  **Search Destination.** Tap Search. Type "Wellington."
8.  **Disambiguate.** Realize "Wellington" is too broad. Type "Simcoe."
9.  **Select Pin.** Choose between 3 overlapping pins.
10. **Analyze.** See destination dock availability.

**Total Clicks/Interactions:** ~8-12.
**Cognitive Load:** High. (Map reading, filtering, decision making).
**Verdict:** "Death by a thousand cuts." The user is forced to learn the UI, rather than the UI serving the user.

---

### Journey B: The TUI (The Solution)
*Goal: Check availability for morning commute.*

1.  **Open Terminal.** (Cmd+Space / Hotkey).
2.  **Type Command.** `bikes`.
3.  **Read Output.**

**Total Clicks/Interactions:** 1 command.
**Cognitive Load:** Near Zero.
**Verdict:** Instant, actionable intelligence.

## 6. Key Design Decisions & Reasoning

### Why a TUI (Terminal User Interface)?
*   **Proximity to Workflow:** For the target demo, the terminal is already open.
*   **Speed:** Text renders faster than maps.
*   **Precision:** We don't need a map. We know where "Home" is. We need *numbers*.
*   **No "App Fatigue":** No context switching to a phone, no waiting for animations.

### Why Python & Rich?
*   **Rich Library:** Allows for beautiful, modern CLI formatting (tables, emojis, progress bars, colors) without the complexity of a full GUI framework.
*   **Standard Library Focus:** We used `urllib` and `json` to minimize dependencies, making the script portable and easy to install.

### The "Simple Statistics" vs. ML Decision
We considered using a Machine Learning model (XGBoost or Prophet) to predict availability but decided against it.
*   **Why Not ML:** ML models are opaque "black boxes," heavy to run, and require constant retraining.
*   **Why Simple Statistics:** Bike commuting is highly cyclical (human behavior).
    *   *The Logic:* A simple mean average of "Net Flow" (Arrivals - Departures) grouped by **Day of Week** and **Hour** captures 90% of the signal.
    *   *Interpretability:* We can explain exactly *why* a prediction is made ("Usually -5 bikes/hr at this time").

## 7. The Prediction Engine: Solving the "Snapshot" Problem
The biggest flaw in the official app is that it provides a **snapshot** (e.g., "5 bikes available"). It does not tell you that 10 minutes ago there were 15, and 10 minutes from now there will be 0.

### The Data Pipeline
1.  **Source:** Toronto Open Data (9 months of ridership history, 5.3 million trips).
2.  **ETL:** We parsed the CSVs to calculate **Net Flow** for every station, for every hour of the week.
    *   *Departure:* Demand for bikes.
    *   *Arrival:* Demand for docks.
3.  **Storage:** Aggregated data is stored in a lightweight (2MB) JSON lookup file. This allows O(1) access time—instant results without querying a database.

### The "Trend-Adjusted" Logic
We created a custom availability algorithm that combines **State + Velocity**:
*   **HIGH Likelihood:** Station has >40% capacity **AND** the historical trend is stable or increasing.
*   **MEDIUM Likelihood:** Station has bikes, **BUT** historically empties fast at this hour.
*   **LOW Likelihood:** Station is empty **OR** is critically low and trending downwards.

This logic powers the **"Depletion Warnings"** (e.g., *⚠️ Often runs low by 8:45 AM on Fridays*), giving the user a "rush factor" that the official app completely lacks.

## 8. What We Shipped
We delivered a standalone executable command `bikes` that prints a dashboard to the terminal.

### Features
*   **Dual-Location View:** Simultaneous status for Origin (Fort York) and Destination (RBC).
*   **Visual Bars:** ASCII progress bars for Bikes vs. Docks vs. E-bikes.
*   **Color Coding:** Green (Good), Yellow (Warning), Red (Critical).
*   **Prediction Context:** A "Likelihood" score and specific warning messages based on historical data.

### Visual Comparison

**The App (Conceptual):**
> [Map View] -> [Pin] -> [Popup] -> "10 Bikes"
> (Requires navigation, tapping, and mental math).

**The TUI (Actual):**
```text
╭─ 🏠 215 Fort York Blvd ──────────────────────────╮
│  🚲 Get a Bike:   MEDIUM ⚠                       │
│     (Often runs low by 8:45am on Fridays)        │
│                                                  │
│  Station          Dist   Bikes       Docks       │
│  Fort York Blvd   37m    ███░░ 15    ████░ 30    │
╰──────────────────────────────────────────────────╯
```

---

## 9. Phase 2: Answering "Should I Bike Today?"

After shipping the initial version, user testing revealed a new friction point: even with all the data displayed, the user still had to **mentally synthesize** two panels of information to answer the fundamental question: *"Should I bike, or should I take transit?"*

### The Insight

A commuter waking up in the morning doesn't want to analyze bike percentages and dock counts. They want a **single, glanceable answer**.

### The Trip Summary Feature

We added an "executive summary" panel at the very top of the output:

```text
╭──────────────────────────────────────────────────────────────────────────────╮
│                   Trip: HIGH - Safe to bike  (Home → Work)                   │
╰──────────────────────────────────────────────────────────────────────────────╯
```

**Key Design Decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Combination method** | Weighted average (60% bikes, 40% docks) | Bikes are gating; docks have workarounds |
| **Gating rule** | LOW bikes = LOW trip | Can't start a trip without a bike |
| **Direction detection** | Time-based (before noon = Home→Work) | Simplest approach for the common case |
| **"Leave by" calculation** | Dynamic: current bikes ÷ depletion rate | Responds to actual conditions |

**The Messages:**

| Trip Confidence | Message |
|-----------------|---------|
| HIGH | "Safe to bike" |
| MEDIUM (dock issue) | "Docks may be tight at work" |
| MEDIUM (time pressure) | "Safe to bike, but leave by 8:30 AM" |
| LOW | "Consider transit/walking" |

### The 800-Meter Error & Setup Wizard

During testing, we discovered the hardcoded coordinates for "215 Fort York Blvd" were **800 meters off**, showing completely wrong stations. The coordinates had been manually estimated rather than geocoded.

**The Problem:**
> "How is it that I was placed 500-800 meters away? There should be a deterministic way to do this."

**The Solution:** A Setup Wizard (`bikes --setup`) that:
1. Accepts a user-typed address
2. Geocodes it using OpenStreetMap (no API key required)
3. Shows a confirmation with Street + Postal Code
4. Saves to `~/.bikes_config.json`

**Why OpenStreetMap over Google Maps?**
Google requires an API key. Asking users to generate Google Cloud credentials would kill adoption. OpenStreetMap is free and accurate enough for Toronto addresses.

### Hyper-Local Predictions

We discovered that averaging predictions across all 5 nearby stations diluted accuracy. A station 300m away filling up doesn't help if the one at your door is empty.

**The Fix:** Predictions now use only the **closest 2 stations**, while the visual list still shows 5 for fallback options.

### The Absolute Floor

Percentage-based logic can mislead:
- 5 bikes at a 10-dock station = 50% → HIGH
- 18 bikes at a 74-dock station = 24% → LOW

But 18 bikes is objectively *more* than 5. A commuter only needs one working bike.

**The Fix:** If there are ≥5 bikes, the likelihood is never LOW, regardless of percentage. This accounts for ~10% damaged bikes and provides a safety buffer.

---

## 10. Phase 3: From Script to System (Real-Time Evolution)

After solving the accuracy issues in Phase 2, we faced an architectural limit. The tool was a "fire-and-forget" script: it ran, printed static text, and died.

**The Problem:**
- Commuters wanted a **"Watch Mode"** (keep it open on a side monitor).
- We wanted to build a **Mobile Widget** eventually.
- The code was "Imperative" (mixed logic and printing), making it impossible to reuse the logic for a server or live display.

### The Architecture Refactor
We fundamentally changed the codebase from **Procedural** to **Functional/Declarative**.

**1. Separation of Concerns (Chef vs. Waiter)**
We split `main()` into two distinct layers:
- **The Brain (`get_dashboard_data`)**: Fetches APIs, calculates predictions, and returns a pure Python Dictionary (Data). It knows *nothing* about the screen.
- **The Face (`build_dashboard_group`)**: Takes that dictionary and builds a tree of Rich objects (Presentation).

**2. The Live Loop**
By decoupling the data, we could wrap the "Face" in a `rich.Live` manager.
- **Default Behavior:** `bikes` now enters a live loop, refreshing every 60 seconds without flickering.
- **Legacy Behavior:** `bikes --once` prints a snapshot and exits (useful for scripts/logs).

**3. Enabling the Ecosystem**
Because `get_dashboard_data` returns raw data (e.g., `bikes: 5`) instead of formatted text (e.g., `\033[32m█████`), we can now easily wrap this function in a Flask server to power an iOS widget.

---

## 11. Phase 4: The Interface Evolution (Menu Bar App)

With the backend architecture modernized, we tackled the next friction point: **Ubiquity**.

### The User Need
> "Something where the user can quickly glance at it... A Mac menu bar item by my clock."

Even opening a terminal is sometimes too much friction. A commuter wants to know the status *before* they even think to ask the question.

### The "Build vs. Buy" Decision
We evaluated three paths to get into the menu bar:
1.  **Native macOS App (Swift):** High effort, best UI.
2.  **Web Widget (MenubarX):** Medium effort, HTML/CSS styling.
3.  **SwiftBar Plugin:** Low effort, reuses our Python script.

We chose **SwiftBar** because it allowed us to leverage our newly refactored "Engine". We didn't need to rewrite the logic in Swift; we just needed to write a new `render_swiftbar()` function in Python.

### The UX Journey: Designing the "Traffic Light"

We iterated rapidly on the visual design to fit high-density information into 20 pixels of screen space.

**Iteration 1: Text-Heavy**
> `🚲 MEDIUM`
> *Critique:* Too wide. Requires reading.

**Iteration 2: The "Double Icon" Glitch**
> `🚲 🟡`
> *User feedback:* "Why are there two bike icons? There should be only one."
> *Root Cause:* We accidentally rendered a text emoji (`🚲`) *and* a system icon (`sfimage=bicycle`) side-by-side.

**Iteration 3: The Traffic Light (Final)**
> `🟡 | sfimage=bicycle`
> *User feedback:* "The text with medium... can be switched to a yellow circle emoji."
> *Result:* A clean, color-coded system.
> *   🟢 = Safe to bike
> *   🟡 = Caution (Trend falling or medium stock)
> *   🔴 = Danger (Empty or rapidly depleting)

### The "Proactive" Engineering Fix
During deployment, we realized a critical flaw: SwiftBar executes scripts using the system Python, which lacks our dependencies (`rich`).
*   **The Fix:** We wrote a custom installer script (`install_swiftbar.sh`) that detects the user's *current* Python environment and hardcodes that path into the plugin. This ensures the app works even if the user relies on virtual environments (`venv` or `conda`).

---

## 12. Conclusion & Learnings
By stripping away the map and focusing on the raw data needs of the commuter, we reduced a 12-step interaction process down to a glance.

The key learning is that **context is king**. Knowing "there are 5 bikes" is useless if you don't know that "5 bikes usually disappear in 10 minutes at this time of day." By fusing real-time API data with historical open data, we created a tool that doesn't just display information—it provides *intelligence*.

### Core Design Principles
*   **Answer the real question first.** Users don't want data; they want decisions. The "Trip Summary" (Safe to Bike vs. Consider Transit/Walking) is more valuable than the raw numbers.
*   **Hardcoding is fragile.** Our 800-meter error proved that geocoding beats manual coordinate entry every time.
*   **Local context matters.** Averaging across 5 stations diluted the signal. Zooming in to the closest 2 revealed the truth.
*   **Absolute thresholds complement percentages.** Percentage-based logic said 18 bikes was "Low availability" (because the dock was huge). But for a human, 18 bikes is plenty. We learned that sometimes, a number is just a number.

### The Engineering Evolution
*   **Phase 1 (Data):** Simple statistics beat complex ML for cyclical human behaviors.
*   **Phase 2 (Interaction):** **The CLI is an interface.** Adding an interactive Setup Wizard bridged the gap between a raw developer script and a user-friendly product.
*   **Phase 2 (Synthesis):** **Algorithmic translation.** We engineered a weighted scoring system to translate raw API data into human decisions ("Safe" vs. "Unsafe"), shifting cognitive load from the user to the machine.
*   **Phase 3 (Architecture):** **Separation of Concerns is the cornerstone of growth.** Decoupling Logic (`get_dashboard_data`) from Display (`render_tui`) transformed a rigid script into a flexible platform.
*   **Phase 4 (Ubiquity):** **Meet the user where they are.** A terminal is great for deep dives, but a menu bar traffic light is superior for "at-a-glance" decision making.


