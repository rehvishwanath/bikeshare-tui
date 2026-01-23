# Engineering Learnings: From Script to System

This document captures the key software engineering concepts and architectural decisions encountered while evolving the Toronto Bike Share TUI from a simple script into a real-time application.

---

## 1. Imperative vs. Declarative: The Pizza Analogy

One of the biggest shifts in "Phase 3" (Real-Time Refactor) was moving from an **Imperative** coding style to a **Declarative** one.

### Imperative (Procedural)
*Like teaching someone to cook.*
> "Walk to the fridge. Open the door. Take out the dough. Close the door. Walk to the counter. Knead the dough for 10 minutes. Add sauce..."

*   **Focus:** The *steps* and the *order*.
*   **The Old Script:** It was imperative. "Fetch data. Now calculate math. Now print the header. Now print the table."
*   **The Downside:** If you want to update the screen, you have to repeat all the steps from start to finish. You can't just "refresh" one part.

### Declarative
*Like ordering at a restaurant.*
> "I want a pepperoni pizza."

*   **Focus:** The *result* (The "What"). You don't care how the chef moves around the kitchen.
*   **The New "Watch Mode":** It is declarative. We built a function (`build_dashboard_group`) that says, "Here is the data structure I want on the screen." We hand that structure to the `Live` manager, and it figures out how to draw (and redraw) it.

---

## 2. The Terminal Illusion

How does "Real-Time" actually work in a terminal that is designed to just print text line-by-line?

### The Old Way (The Illusion of Instant)
Computers are incredibly fast. When the old script ran:
1.  It fetched data (took ~0.5 seconds).
2.  It calculated math (took ~0.0001 seconds).
3.  It printed text line-by-line (took ~0.001 seconds).

To the user's eye, it appeared instantly. But technically, it was just appending text to a log file. Once a line was printed, the script "forgot" about it. It was just ink on paper.

### The New Way (The Live Manager)
When we switched to `bikes` (Watch Mode), we stopped treating the terminal like a scroll of paper and started treating it like a **screen**.

1.  **The Buffer:** The `Live` manager (from the `rich` library) creates a hidden canvas in memory. It draws the entire dashboard on this invisible canvas.
2.  **The Swap:** Once the drawing is complete, it instantly swaps the visible screen with the hidden canvas.
3.  **The Update:** When data changes 60 seconds later, it erases the canvas, redraws the new numbers, and swaps it again. This creates the animation effect without "flickering" or filling your scrollback history.

### "Breaking the Layout"
If you mix these two modes, things break.
*   **The Issue:** If we accidentally left a `print("Error")` statement in the data logic, it would write bytes directly to the terminal `stdout` while the Live Manager was trying to paint the screen.
*   **The Result:** It's like throwing a bucket of paint on a canvas while an artist is painting. The artist (Live Manager) loses track of where their brush was, and the layout gets garbled. This is why strict separation of **Data Logic** (no printing) and **Display Logic** (only printing) is crucial.

---

## 3. Data vs. Presentation: Enabling Mobile

The most critical architectural change was separating the **Data** from the **Presentation**.

### The Old Output (Presentation)
The old script produced **Text with Color Codes**.
If you looked at the raw output, it didn't look like `5 bikes`. It looked like:
`\033[32m█████\033[0m 5 bikes`

*   **The Problem:** A mobile app or web server doesn't know what `\033[32m` means. It doesn't want a picture of a progress bar made of text. It wants to know: `bikes: 5`.

### The Refactor (Data)
By creating `get_dashboard_data()`, we stopped calculating colors and bars in the logic layer. We started calculating **Raw Facts**.

*   **Old Logic:** "Create a green string that is 5 characters long."
*   **New Logic:** "Return the number 5."

### Why this enables a System
Now that we have a function that returns a Python Dictionary (`{ "home_bikes": 5 }`), we can wrap that in anything:
*   **TUI:** The terminal wraps it in a colored panel.
*   **Server:** A Flask app wraps it in a JSON response.
*   **Mobile:** An iOS widget reads the JSON and draws its own green bar using native graphics.

**Summary:** We separated the **Chef** (Logic) from the **Waiter** (Display). Before, the Chef was bringing the food to the table himself. Now, the Chef just cooks, and we can hire a Waiter (Terminal) or a Delivery Driver (Mobile App) to serve it.

---

## 4. Script vs. Application: The Mental Model

A key question arose during our refactor: *What makes this an "Application" now? Is it just a script that loops?*

While technically it is a loop, the distinction lies in the architectural intent.

### The Script (Procedural)
*   **Mental Model:** A Checklist.
*   **Action:** "Fetch data. Print data. Exit."
*   **Characteristics:** It has a start and an end. It is short-lived. To refresh the data, you must restart the checklist from step 1.

### The Application (System)
*   **Mental Model:** A Robot.
*   **Action:** "Stand in the kitchen. Every 60 seconds, check the sensors. Update the display."
*   **Characteristics:** It has a **Lifecycle** and **State**. It is alive and reacting to time.

### The Cornerstone: Separation of Concerns
Is Separation of Concerns (SoC) just for applications? No, but it is the cornerstone that allows a script to *become* a system.
*   Because we separated `get_dashboard_data` (The Logic) from `build_dashboard_group` (The UI), our code assumes **growth and change**.
*   Today the "View" is a Terminal. Tomorrow it could be a Web Server. The "Model" doesn't care.

---

## 5. The Architecture of Our Loop

We moved from a linear flow to a **Model-View-Controller (MVC)** pattern inside a loop:

1.  **The Controller (`main`)**: The Boss. It orchestrates the lifecycle. It doesn't know how to fetch data or draw pixels. It just manages the schedule.
2.  **The Model (`get_dashboard_data`)**: The Brain. It performs the heavy lifting (API calls, math) and returns raw data (Dictionaries). It has no idea a screen exists.
3.  **The View (`build_dashboard_group`)**: The Artist. It takes raw data and builds a visual blueprint (Rich objects).
4.  **The Engine (`Live` Manager)**: The Painter. It takes the blueprint and renders it to the screen using **Double Buffering**.

### Double Buffering (The "No Flicker" Trick)
Why does the new version look so smooth?
*   **Direct Printing:** Like writing on a whiteboard with a marker. To update, you must erase (flicker) and rewrite.
*   **Live Manager:** Like having two whiteboards. The engine draws the new frame on a hidden board, then instantly swaps it with the visible one. The user never sees the "drawing" process, only the result.

---

## 6. The API Layer: How Flask "Wraps" Logic

Moving from a local script to a "Private Cloud" API required understanding three concepts: Wrapping, Exposing, and Translation.

### 1. The Translator (Flask)
Your Python script speaks "Python" (Dictionaries, Lists, Integers). The Internet speaks "HTTP" (GET Requests, JSON strings).
*   **Flask** acts as the translator. It takes an incoming HTTP request, translates it into a Python function call, waits for the result, and translates the Python Dictionary back into a JSON string response.

### 2. "Wrapping" the Logic
We took our existing engine (`get_dashboard_data`) and "wrapped" it in a web route using a **Decorator**:

```python
@app.route('/status')  # <--- The Door
def status():
    data = get_dashboard_data()  # <--- The Logic
    return jsonify(data)  # <--- The Translation
```

This tells Flask: *"When someone knocks on the door labeled `/status`, run the engine and give them the result."* We didn't have to rewrite the engine; we just gave it a new door.

### 3. "Exposing" the Server (IPs & Ports)
To let the iPhone reach the Mac, we had to configure the "Address":

*   **IP Address (The Building):** We used Tailscale (`100.x.y.z`) to give the Mac a stable, secure address reachable from anywhere in the world.
*   **Port (The Apartment):** We assigned Port `5001` to our specific script. When a data packet arrives at the Mac, the OS checks the port number to decide which program gets the message.
*   **Listening (`0.0.0.0`):** By default, Flask only listens to "internal" whispers (`localhost`). We configured it to listen to "shouts from the street" (`0.0.0.0`), allowing the Tailscale interface to connect.


