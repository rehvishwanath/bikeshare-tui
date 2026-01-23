// Bike Share Widget - Option 5 Design
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
  w.backgroundColor = new Color("#0f172a"); // bg-slate-900
  
  if (data.error) {
    let t = w.addText("⚠️ Error");
    t.textColor = Color.red();
    return w;
  }

  // --- DATA PARSING ---
  let confidence = data.trip_summary.confidence;
  let message = data.trip_summary.message;
  let fromLoc = data.direction.from;
  let toLoc = data.direction.to;
  
  // Colors (Tailwind approximation)
  const cSlate700 = new Color("#334155");
  const cSlate500 = new Color("#64748b");
  const cBlueActive = new Color("#3b82f6", 0.2); // Blue-500/20
  const cBlueIcon = new Color("#60a5fa"); // Blue-400
  const cGrayIcon = new Color("#94a3b8"); // Slate-400
  
  let statusColor = new Color("#34d399"); // Emerald-400 (Default Green)
  if (confidence == "MEDIUM") statusColor = new Color("#fbbf24"); // Amber-400
  if (confidence == "LOW") statusColor = new Color("#f87171"); // Red-400

  // Icons logic
  let isFromHome = fromLoc === "Home";
  let leftIcon = isFromHome ? "house.fill" : "briefcase.fill";
  let rightIcon = isFromHome ? "briefcase.fill" : "house.fill";
  
  // --- UI DRAWING ---
  
  // 1. Top Section (Row with Icons)
  let topStack = w.addStack();
  topStack.layoutHorizontally();
  topStack.centerAlignContent();
  
  // Left Icon (Active/Start)
  addCircleIcon(topStack, leftIcon, cBlueActive, cBlueIcon);
  
  // Connector Line
  topStack.addSpacer(4);
  let lineStack = topStack.addStack();
  lineStack.layoutHorizontally();
  lineStack.centerAlignContent();
  
  let arrow = lineStack.addImage(SFSymbol.named("chevron.right").image);
  arrow.imageSize = new Size(12, 12);
  arrow.tintColor = statusColor;
  arrow.resizable = false;
  
  topStack.addSpacer(4);
  
  // Right Icon (Inactive/End)
  addCircleIcon(topStack, rightIcon, cSlate700, cGrayIcon);
  
  // Spacer to push text down
  w.addSpacer(); // Flex spacer
  
  // 2. Bottom Section (Text)
  let textStack = w.addStack();
  textStack.layoutVertically();
  textStack.centerAlignContent(); // Center horizontally
  
  // "Safe to bike"
  let statusText = textStack.addText(message);
  statusText.font = Font.boldSystemFont(18);
  statusText.textColor = statusColor;
  statusText.centerAlignText();
  
  // "to home"
  let dirText = textStack.addText(`to ${toLoc.toLowerCase()}`);
  dirText.font = Font.systemFont(12);
  dirText.textColor = cSlate500;
  dirText.centerAlignText();
  
  // "Leave by" (Optional, extra context)
  if (data.trip_summary.leave_by) {
    textStack.addSpacer(2);
    let timeText = textStack.addText(`Leave: ${data.trip_summary.leave_by}`);
    timeText.font = Font.boldSystemFont(10);
    timeText.textColor = new Color("#fbbf24");
    timeText.centerAlignText();
  }

  // Refresh interval
  w.refreshAfterDate = new Date(Date.now() + 1000 * 60 * 15);
  
  return w;
}

// Helper: Add a colored circle stack with an SF Symbol inside
function addCircleIcon(parentStack, symbolName, bgColor, iconColor) {
  let stack = parentStack.addStack();
  stack.size = new Size(32, 32);
  stack.layoutHorizontally();
  stack.centerAlignContent();
  
  // Draw Circle Background using DrawContext (just the circle)
  let ctx = new DrawContext();
  ctx.size = new Size(32, 32);
  ctx.opaque = false;
  ctx.setFillColor(bgColor);
  ctx.fillEllipse(new Rect(0, 0, 32, 32));
  stack.backgroundImage = ctx.getImage();
  
  // Add Icon on top (centered via stack layout)
  // We need to ensure the icon centers. 
  // Stacks center vertically by default if centerAlignContent is set.
  // Horizontal centering requires addSpacer on both sides if not full width.
  stack.addSpacer();
  let sym = SFSymbol.named(symbolName);
  let widgetImg = stack.addImage(sym.image);
  widgetImg.tintColor = iconColor;
  widgetImg.imageSize = new Size(16, 16);
  stack.addSpacer();
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
