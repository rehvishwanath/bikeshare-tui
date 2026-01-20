#!/bin/bash

# SwiftBar Plugin Installer for Toronto Bike Share TUI

# Default directory or user provided argument
SWIFTBAR_DIR="${1:-$HOME/Library/Application Support/SwiftBar/Plugins}"
PLUGIN_NAME="bikes.1m.sh"
PLUGIN_PATH="$SWIFTBAR_DIR/$PLUGIN_NAME"

# Get absolute path to src/bikes.py
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
BIKES_SCRIPT="$REPO_ROOT/src/bikes.py"

# Verify SwiftBar directory exists
if [ ! -d "$SWIFTBAR_DIR" ]; then
    echo "❌ SwiftBar plugins directory not found at:"
    echo "   $SWIFTBAR_DIR"
    echo ""
    echo "Please create this directory or launch SwiftBar to select your plugin folder."
    exit 1
fi

# Create the wrapper script
echo "#!/bin/bash" > "$PLUGIN_PATH"
echo "" >> "$PLUGIN_PATH"
# Use the current python interpreter to ensure dependencies (like rich) are found
PYTHON_PATH="$(which python3)"
echo "\"$PYTHON_PATH\" \"$BIKES_SCRIPT\" --swiftbar" >> "$PLUGIN_PATH"

chmod +x "$PLUGIN_PATH"

echo "✅ Installed SwiftBar plugin to:"
echo "   $PLUGIN_PATH"
echo ""
echo "You should see the bicycle icon in your menu bar momentarily!"
