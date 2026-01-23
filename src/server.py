from flask import Flask, jsonify, request, abort
import sys
import os
import secrets

# Add the current directory to path so we can import bikes
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bikes import get_dashboard_data, load_config, LOCATIONS

app = Flask(__name__)

# Security: Load or Generate API Key
API_KEY_FILE = os.path.expanduser("~/.bikes_api_key")

def get_api_key():
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, 'r') as f:
            return f.read().strip()
    else:
        # Generate a new strong key
        key = secrets.token_urlsafe(16)
        with open(API_KEY_FILE, 'w') as f:
            f.write(key)
        print(f"🔑 Generated new API Key: {key}")
        print(f"Saved to {API_KEY_FILE}")
        return key

API_KEY = get_api_key()

@app.route('/')
def home():
    """Health check."""
    return "🚲 Bike Share API is running. Use /status with your API key."

@app.route('/status')
def status():
    """Return the dashboard data as JSON."""
    # Check Auth
    client_key = request.headers.get('X-API-Key')
    # Also allow query param for simple testing ?key=...
    if not client_key:
        client_key = request.args.get('key')
        
    if client_key != API_KEY:
        abort(401, description="Invalid API Key")

    # Load config logic (reused from bikes.py main)
    locations = load_config()
    if not locations:
        locations = LOCATIONS
        # Remap default locations if using hardcoded ones
        if "215 Fort York Blvd" in locations:
            locations = {
                "Home": locations["215 Fort York Blvd"],
                "Work": locations["155 Wellington St (RBC Centre)"]
            }

    data = get_dashboard_data(locations)
    
    if not data:
        return jsonify({"error": "Failed to fetch data"}), 500
        
    return jsonify(data)

if __name__ == '__main__':
    print(f"🚀 Server starting on port 5001...")
    print(f"🔑 Your API Key: {API_KEY}")
    print(f"🔗 Test URL: http://localhost:5001/status?key={API_KEY}")
    app.run(host='0.0.0.0', port=5001)
