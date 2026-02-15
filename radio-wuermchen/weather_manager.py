# weather_manager.py

import subprocess
import time
import json
from pathlib import Path
import os

# --- CONFIGURATION ---
# Assuming this file lives in the same directory as the orchestrator.
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
SCRAPER_SCRIPT = BASE_DIR / "scraper.py"
WEATHER_TEMPLATE = BASE_DIR / "templates" / "weather_vienna.txt"
WEATHER_RESULT = BASE_DIR / "templates" / "weather_result.json"
WEATHER_CACHE_MAX_AGE = 1800  # seconds (30 min) - don't re-scrape more often than this
PYTHON_BIN = "C:\\Program Files\\Python311\\python.exe"

# --- HELPERS (Stubs for functions needed from orchestrator) ---
# In a real project, these would be imported, but here we stub what's needed for execution isolation.
def load_json(path):
    try:
        with open(str(path), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def log(msg):
    # For now, print to stdout, the orchestrator will handle logging.
    # In a real scenario, this would import the orchestrator's log function.
    print(f"[WEATHER_MANAGER] {msg}")

# --- CORE FUNCTION ---

def get_weather_forecast():
    """Run the scraper for weather and return the forecast text, or None."""
    try:
        # Check cache age - don't scrape too often
        if os.path.exists(WEATHER_RESULT):
            age = time.time() - os.path.getmtime(WEATHER_RESULT)
            if age < WEATHER_CACHE_MAX_AGE:
                cached = load_json(WEATHER_RESULT)
                forecast = cached.get("forecast")
                if forecast:
                    log(f"Using cached weather ({int(age)}s old)")
                    return forecast

        log("Fetching fresh weather forecast...")
        result = subprocess.run(
            [PYTHON_BIN, str(SCRAPER_SCRIPT), str(WEATHER_TEMPLATE)],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=20
        )
        if result.returncode != 0:
            log(f"Weather scrape failed: {result.stderr.strip()}")
            return None

        data = load_json(WEATHER_RESULT)
        forecast = data.get("forecast")
        if forecast:
            log(f"Weather fetched: {forecast[:80]}...")
        return forecast
    except Exception as e:
        log(f"Weather fetch error: {e}")
        return None
