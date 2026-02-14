# DJ Brain (Black Box) - Google Gemini Edition
#
# Standalone LLM-powered DJ that calls the Google Gemini API directly.
# No OpenClaw dependency.
#
# Interface (file-based):
#   Input:  dj_request.json  - context about what just played, listener input, etc.
#   Output: dj_response.json - track suggestion + track file path
#   Config: dj_config.json   - API key, model, DJ personality settings
#
# Usage:
#   python dj_brain.py
#
# To swap LLM providers, only this file and dj_config.json need to change.

import json
import sys
import os
import google.genai as genai
from google import genai as genai_client
import requests
import time

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "dj_config.json")
REQUEST_FILE = os.path.join(SCRIPT_DIR, "dj_request.json")
RESPONSE_FILE = os.path.join(SCRIPT_DIR, "dj_response.json")
HISTORY_FILE = os.path.join(SCRIPT_DIR, "dj_history.json")

# --- HELPERS ---
def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return empty list for history, or empty dict for config/request/response
        if path.endswith("history.json"):
            return []
        return {}
    except json.JSONDecodeError as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
        return {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_history():
    """Load recent DJ history (last N tracks played + announcements)."""
    data = load_json(HISTORY_FILE)
    if data and isinstance(data, list):
        return data[-10:]  # keep last 10 entries
    return []

def save_history(history, new_entry):
    """Append a new entry to history and save (keep last 20)."""
    history.append(new_entry)
    history = history[-20:]
    save_json(HISTORY_FILE, history)

# --- GEMINI API CALL ---
def call_gemini(config, system_prompt, user_message):
    """Call the Gemini API using the structure found in Google's current examples."""
    try:
        api_key = config["api_key"]
        model_name = config["model"]

        # FIX: Initialize Client explicitly and pass API key. Remove global configure().
        client = genai_client.Client(api_key=api_key)
        
        # Use the client's generate_content method, matching REST/new SDK structure
        response = client.models.generate_content(
            model=model_name,
            contents=[system_prompt, user_message]
        )
        
        # Extract text from response
        if response.candidates and response.candidates[0].content.parts:
            return response.text
        else:
            print(f"API Response Empty/Failed: {response.prompt_feedback}", file=sys.stderr)
            return None
            
    except Exception as e:
        print(f"Gemini API Error: {e}", file=sys.stderr)
        return None

# --- DJ LOGIC ---
def build_system_prompt(config):
    """Build the system prompt that defines the DJ's personality."""
    dj_name = config.get("dj_name", "DJ Flash")
    station_name = config.get("station_name", "Radio Würmchen")
    language = config.get("language", "English")
    
    diversity_mandate = (
        "If there is no specific listener request, you MUST make an effort to "
        "suggest a track outside of the Alternative Rock/Grunge genre based on the "
        "history of the last 5 tracks. For example, alternate between Rock, Pop, and Electronic/Trip-Hop."
    )
    
    return f"""You are {dj_name}, the DJ of {station_name}. Your responses MUST be 100% valid JSON.
{dj_name}'s Style: Natural, energetic, and concise. Avoid technobabble and hyperbole.
{diversity_mandate}
Output Format: Provide a JSON object with EXACTLY two keys: "track" and "announcement".
- "track": The suggested next track in "Artist - Title" format.
- "announcement": A short (1-3 sentence) natural introduction/transition.

Example JSON:
{{"track": "Fleetwood Mac - Dreams", "announcement": "That was a classic! Now let's ease into something smooth with Fleetwood Mac and their timeless Dreams."}}"""

def build_user_message(request_data, history):
    """Build the user message with context for the DJ."""
    parts = []

    last_track = request_data.get("last_track", "Unknown")
    parts.append(f"The track that just played was: {last_track}")

    # Include recent history for variety
    if history:
        recent = [entry.get("track", "?") for entry in history[-5:]]
        parts.append(f"HISTORY BLOCKLIST: You MUST NOT suggest any track found in this list unless fulfilling a specific listener request that names it: {', '.join(recent)}")

    # Listener input if any
    listener_input = request_data.get("listener_input")
    if listener_input:
        parts.append(f"A listener has requested or commented: {listener_input}")

    # Any special instructions
    instructions = request_data.get("instructions")
    if instructions:
        parts.append(f"System instruction for this turn: {instructions}")

    parts.append("Select the next appropriate track and write the announcement.")
    return "\n".join(parts)

def parse_dj_response(raw_text):
    """Parse the DJ's JSON response. Returns dict with 'track' and 'announcement', or None."""
    if not raw_text:
        return None

    # Gemini often returns clean text, but we clean up potential markdown fences just in case
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        data = json.loads(text)
        if "track" in data and "announcement" in data:
            return data
        else:
            print(f"DJ response missing required keys: {data}", file=sys.stderr)
            return None
    except json.JSONDecodeError as e:
        print(f"Failed to parse DJ response as JSON: {e}", file=sys.stderr)
        print(f"Raw response: {raw_text}", file=sys.stderr)
        return None

# --- MAIN ---
def main():
    # Load config
    config = load_json(CONFIG_FILE)
    if not config:
        print("ERROR: Cannot load dj_config.json", file=sys.stderr)
        sys.exit(1)

    if config.get("api_key", "").startswith("YOUR_"):
        print("ERROR: Please set your API key in dj_config.json", file=sys.stderr)
        sys.exit(1)

    # Load request
    request_data = load_json(REQUEST_FILE)
    if not request_data:
        print("ERROR: Cannot load dj_request.json. Cannot proceed.", file=sys.stderr)
        sys.exit(1)

    # Load history (now handles missing file)
    history = load_history()

    # Build prompts
    system_prompt = build_system_prompt(config)
    user_message = build_user_message(request_data, history)

    # Call LLM
    print(f"Calling {config.get('model')}...")
    raw_response = call_gemini(config, system_prompt, user_message)

    if not raw_response:
        print("ERROR: No response from LLM.", file=sys.stderr)
        save_json(RESPONSE_FILE, {"error": "No response from LLM"})
        sys.exit(1)

    # Parse response
    parsed = parse_dj_response(raw_response)
    if not parsed:
        print("ERROR: Could not parse DJ response.", file=sys.stderr)
        save_json(RESPONSE_FILE, {"error": "Invalid DJ response", "raw": raw_response})
        sys.exit(1)

    # Save response
    save_json(RESPONSE_FILE, parsed)
    print(f"DJ suggests: {parsed['track']}")

    # Update history
    save_history(history, {
        "track": parsed["track"],
        "last_track": request_data.get("last_track", "Unknown")
    })

    sys.exit(0)

if __name__ == "__main__":
    main()