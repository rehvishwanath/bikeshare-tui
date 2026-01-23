// Bike Share Traffic Light Widget
// Copy this into Scriptable App on iOS

// --- CONFIGURATION ---
const API_KEY = "j0viWMEnrzwEGzqWiGXU4A"; // Your generated key
const SERVER_HOST = "100.69.233.114:5001"; // Your Tailscale IP
const API_URL = `http://${SERVER_HOST}/status?key=${API_KEY}`;

// --- MAIN ---
if (config.runsInWidget) {
  let widget = await createWidget();
  Script.setWidget(widget);
} else {
  let widget = await createWidget();
  await widget.presentSmall();
}
Script.complete();

async function createWidget() {
  let data = await fetchData();
  
  let w = new ListWidget();
  w.backgroundColor = new Color("#1C1C1E"); // Dark gray background
  
  if (data.error) {
    let t = w.addText("⚠️ Error");
    t.textColor = Color.red();
    return w;
  }

  // Extract Data
  let confidence = data.trip_summary.confidence; // HIGH, MEDIUM, LOW
  let message = data.trip_summary.message; // "Safe to bike"
  let direction = data.direction.to; // "Work" or "Home"
  
  // Colors
  let statusColor = Color.gray();
  if (confidence == "HIGH") statusColor = new Color("#30D158"); // Green
  if (confidence == "MEDIUM") statusColor = new Color("#FFD60A"); // Yellow
  if (confidence == "LOW") statusColor = new Color("#FF453A"); // Red

  // --- UI DRAWING ---
  
  // 1. Direction Label
  let headerStack = w.addStack();
  headerStack.layoutHorizontally();
  
  let title = headerStack.addText(`To ${direction}`);
  title.font = Font.boldSystemFont(12);
  title.textColor = Color.gray();
  
  headerStack.addSpacer();
  
  w.addSpacer(8);
  
  // 2. Traffic Light (Circle + Icon)
  let statusStack = w.addStack();
  statusStack.centerAlignContent();
  
  // Draw Circle
  let circle = statusStack.addImage(drawCircle(statusColor));
  circle.imageSize = new Size(16, 16);
  
  statusStack.addSpacer(6);
  
  // Draw Bike Icon (using SF Symbol)
  let sfSymbol = SFSymbol.named("bicycle");
  let icon = statusStack.addImage(sfSymbol.image);
  icon.imageSize = new Size(24, 24);
  icon.tintColor = Color.white();
  
  w.addSpacer(8);
  
  // 3. Message
  let msgText = w.addText(message);
  msgText.font = Font.systemFont(14);
  msgText.textColor = statusColor;
  msgText.minimumScaleFactor = 0.8; // Shrink if too long
  
  // 4. "Leave By" Time (if exists)
  if (data.trip_summary.leave_by) {
    w.addSpacer(4);
    let timeText = w.addText(`Leave: ${data.trip_summary.leave_by}`);
    timeText.font = Font.boldSystemFont(12);
    timeText.textColor = Color.orange();
  }

  // Refresh every 15 mins
  w.refreshAfterDate = new Date(Date.now() + 1000 * 60 * 15);
  
  return w;
}

async function fetchData() {
  try {
    let req = new Request(API_URL);
    let json = await req.loadJSON();
    return json;
  } catch (e) {
    return { error: e.message };
  }
}

// Helper to draw a colored circle image
function drawCircle(color) {
  let ctx = new DrawContext();
  ctx.size = new Size(32, 32);
  ctx.opaque = false;
  ctx.setFillColor(color);
  ctx.fillEllipse(new Rect(0, 0, 32, 32));
  return ctx.getImage();
}
