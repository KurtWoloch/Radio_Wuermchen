# DJ Brain (Black Box) - Google Gemini Edition
#
# Usage: python dj_brain.py
#
# Listens for a request file, calls Gemini, and writes the response.
#
# Dependencies: google-genai

import json
import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path
from google import genai as genai_client
from google.genai import types

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "dj_config.json")
REQUEST_FILE = os.path.join(SCRIPT_DIR, "dj_request.json")
RESPONSE_FILE = os.path.join(SCRIPT_DIR, "dj_response.json")
HISTORY_FILE = os.path.join(SCRIPT_DIR, "dj_history.json")
WISHLIST_FILE = os.path.join(SCRIPT_DIR, "Wishlist.txt")
TTS_GENERATOR_SCRIPT = os.path.join(SCRIPT_DIR, "tts_generate.py")
PYTHON_BIN = "C:\\Program Files\\Python311\\python.exe"

# --- HELPERS ---
def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error reading JSON file {path}: {e}", file=sys.stderr)
        return {}

def load_history():
    """Load DJ history, returns empty list if file missing."""
    return load_json(HISTORY_FILE)

def save_history(history):
    """Save DJ history."""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving history: {e}", file=sys.stderr)
        return False

MAX_HISTORY_ENTRIES = 50  # Keep last 50 tracks in history

def append_to_history(track, announcement):
    """Adds new entry to history and trims to MAX_HISTORY_ENTRIES."""
    history = load_history()
    if not isinstance(history, list):
        history = []
        
    history.append({
        "timestamp": datetime.now().isoformat(),
        "track": track,
        "announcement": announcement
    })
    
    # Trim oldest entries if history exceeds max size
    if len(history) > MAX_HISTORY_ENTRIES:
        history = history[-MAX_HISTORY_ENTRIES:]
    
    save_history(history)

def append_to_wishlist(track):
    """Adds failed suggestion to wishlist."""
    try:
        with open(WISHLIST_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().isoformat()} | {track}\n")
    except Exception as e:
        print(f"Error writing to wishlist: {e}", file=sys.stderr)

def call_gemini(config, system_prompt, user_message):
    """Call the Gemini API using the structure found in Google's current examples."""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("ERROR: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
            return None

        client = genai_client.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model=config["model"],
            contents=[system_prompt, user_message],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],
                temperature=config.get("temperature", 0.7)
            )
        )

        if not response.candidates or not response.candidates[0].content.parts:
            print(f"API Response Empty/Failed: {response.prompt_feedback}", file=sys.stderr)
            return None
            
        return response.candidates[0].content.parts[0].text

    except Exception as e:
        print(f"Gemini API Call Failed: {e}", file=sys.stderr)
        return None

def build_system_prompt(config):
    """Build the system prompt that defines the DJ's personality."""
    dj_name = config.get("dj_name", "DJ Flash")
    station_name = config.get("station_name", "Radio Würmchen")
    language = config.get("language", "German")
    
    diversity_mandate = (
        "If there is no specific listener request, you MUST make an effort to "
        "suggest a track from a DIFFERENT genre than the last 2-3 tracks. "
        "Draw from a wide range: Pop, Rock, New Wave, Indie, Punk, Metal, Soul, Funk, "
        "Disco, Schlager, Austropop, Singer-Songwriter, Classical Crossover, Comedy, "
        "Electronic, 80s, 90s, 2000s, World Music, etc. Avoid repeating the same genre twice in a row."
    )
    
    now = datetime.now().strftime("%A, %H:%M")
    
    return f"""You are {dj_name}, the DJ of {station_name}. The current time is {now}. Your responses MUST be 100% valid JSON.
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
        recent = [entry.get("track", "?") for entry in history[-10:]]
        parts.append(f"HISTORY BLOCKLIST: You MUST NOT suggest any track found in this list unless fulfilling a specific listener request that names it: {', '.join(recent)}")

    # Listener input if any
    listener_input = request_data.get("listener_input")
    if listener_input:
        parts.append(f"A listener has requested or commented: {listener_input}")
    else:
        # --- NEW INSTRUCTION FOR LONGER ANNOUNCEMENTS ---
        parts.append("Since there is no specific listener request, your announcement should be more detailed and engaging (2-3 sentences) about the song or artist before introducing the track.")
        
    # Any special instructions
    instructions = request_data.get("instructions")
    if instructions:
        parts.append(f"System instruction for this turn: {instructions}")

    parts.append("Select the next appropriate track and write the announcement.")
    return "\n".join(parts)

def parse_dj_response(raw_text):
    """Parses the raw JSON string response from the DJ Brain into a Python dict."""

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
        sys.exit(1)

    # Parse and save result
    response = parse_dj_response(raw_response)

    if response:
        print(f"DJ Suggestion: {response['track']}")
        append_to_history(response["track"], response["announcement"])
        
        with open(RESPONSE_FILE, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2)
        
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()