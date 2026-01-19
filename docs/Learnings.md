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
