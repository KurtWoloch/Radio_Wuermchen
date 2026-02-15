# DJ Orchestrator (Glue Script)
#
# Monitors the queue_low.signal file, triggers the standalone DJ,
# handles TTS generation for the announcement, and feeds the results
# back into the main queue.

import subprocess
import sys
import os
import time
import json
from pathlib import Path
import re

# --- CONFIGURATION ---
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = BASE_DIR / "queue.txt"
SIGNAL_FILE = BASE_DIR / "queue_low.signal"
REQUEST_FILE = BASE_DIR / "dj_request.json"
RESPONSE_FILE = BASE_DIR / "dj_response.json"
PLAYLIST_FILE = BASE_DIR / "music.playlist"
TTS_GENERATOR_SCRIPT = BASE_DIR / "tts_generate.py"
DJ_BRAIN_SCRIPT = BASE_DIR / "dj_brain.py"
LOG_FILE = BASE_DIR / "orchestrator.log"
WISHLIST_FILE = BASE_DIR / "Wishlist.txt"
LISTENER_REQUEST_FILE = BASE_DIR / "listener_request.txt" # NEW: Listener input file

SCRAPER_SCRIPT = BASE_DIR / "scraper.py"
WEATHER_TEMPLATE = BASE_DIR / "templates" / "weather_vienna.txt"
WEATHER_RESULT = BASE_DIR / "templates" / "weather_result.json"
WEATHER_CACHE_MAX_AGE = 1800  # seconds (30 min) - don't re-scrape more often than this

NEWS_MANAGER_SCRIPT = BASE_DIR / "news_manager.py"
NEWS_HEADLINES_INTERVAL = 3600  # seconds (60 min) - how often to do a full headlines segment
NEWS_STATE_FILE = BASE_DIR / "news_state.json"  # tracks last headlines time

ANNOUNCEMENT_SLOTS = 10  # number of rotating announcement files
ANNOUNCEMENT_MIN_AGE = 1800  # seconds (30 min) before a slot can be reused

PYTHON_BIN = "C:\\Program Files\\Python311\\python.exe"
POLL_INTERVAL = 3  # seconds between checks
MAX_ARTIST_SUGGESTIONS = 50 # Maximum tracks to offer the DJ if suggestion fails
MAX_DJ_ATTEMPTS = 5 # Maximum times to re-prompt the DJ per signal event

# --- HELPERS ---
def log(msg):
    """Write log messages to a file."""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def load_json(path):
    """Load JSON data, handling missing files gracefully."""
    path_str = str(path)
    try:
        with open(path_str, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        if path_str.endswith("history.json"):
            return []
        return {}
    except json.JSONDecodeError as e:
        log(f"Error reading JSON file {path_str}: {e}")
        return {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def read_last_line(path):
    """Reads the last non-empty line from a file."""
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            if file_size == 0:
                return None
            
            # Read backwards in chunks
            chunk_size = 1024
            buffer = b''
            while f.tell() > 0:
                read_size = min(chunk_size, f.tell())
                f.seek(-read_size, os.SEEK_CUR)
                chunk = f.read(read_size)
                buffer = chunk + buffer
                
                # Check if we found a newline within the chunk
                if b'\n' in chunk:
                    return buffer.split(b'\n')[-2].decode('utf-8').strip()
                
                # If we are at the start of the file and found no newline, the whole file is one line
                if f.tell() == 0:
                    return buffer.decode('utf-8').strip()

            return buffer.decode('utf-8').strip()
    except Exception as e:
        log(f"Error reading last line from {path}: {e}")
        return None

def delete_signal():
    """Delete the signal file."""
    try:
        os.remove(SIGNAL_FILE)
        log("Signal file deleted.")
    except FileNotFoundError:
        pass

def read_and_clear_listener_request():
    """Read listener request from file and delete the file."""
    try:
        with open(LISTENER_REQUEST_FILE, 'r', encoding='utf-8') as f:
            request = f.read().strip()
        
        # Delete the file immediately after reading
        os.remove(LISTENER_REQUEST_FILE)
        log("Listener request read and file deleted.")
        return request if request else None
    except FileNotFoundError:
        return None
    except Exception as e:
        log(f"Error reading/clearing listener request file: {e}")
        return None

# --- QUEUE MANAGEMENT ---
def append_to_queue(track_path):
    """Append a track path to the queue file."""
    with open(QUEUE_FILE, 'a', encoding='utf-8') as f:
        f.write(track_path + '\n')
    log(f"Appended to queue: {os.path.basename(track_path)}")

def append_to_wishlist(track_suggestion):
    """Append a track suggestion to the Wishlist file."""
    with open(WISHLIST_FILE, 'a', encoding='utf-8') as f:
        f.write(track_suggestion + '\n')
    log(f"Appended to wishlist: {track_suggestion}")

# --- ARTIST MATCHING ---
def parse_artist_from_suggestion(suggestion):
    """Extracts the artist part from an 'Artist - Title' string."""
    if " - " in suggestion:
        return suggestion.split(" - ", 1)[0].strip()
    return None

def clean_suggestion_for_matching(suggestion):
    """Strips versioning/subtitles from the suggested track name for better matching."""
    # Remove parenthetical notes like (live), (extended), (album version), etc.
    cleaned = re.sub(r'\s*\(.*\)\s*', ' ', suggestion).strip()
    # Remove features (feat. X) as they often cause mismatches if not in library tag
    cleaned = re.sub(r'\s*ft\.\s*.*|\s*feat\.\s*.*', '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned

def find_artist_alternatives(artist_name, playlist, max_results=MAX_ARTIST_SUGGESTIONS):
    """Finds up to max_results tracks from the playlist matching the artist name."""
    alternatives = []
    for p_track in playlist:
        filename = os.path.basename(p_track)
        if artist_name.lower() in filename.lower():
            alternatives.append(p_track)
            if len(alternatives) >= max_results:
                break
    return alternatives

# --- WEATHER ---
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

# --- NEWS ---

def load_news_state():
    """Load persistent news state (last headlines time, etc.)."""
    return load_json(NEWS_STATE_FILE) or {'last_headlines_at': 0}

def save_news_state(state):
    save_json(NEWS_STATE_FILE, state)

def news_update():
    """Run news_manager.py update. Returns True on success."""
    try:
        result = subprocess.run(
            [PYTHON_BIN, str(NEWS_MANAGER_SCRIPT), "update"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=60
        )
        log(f"News update: {result.stdout.strip()}")
        if result.returncode != 0:
            log(f"News update error: {result.stderr.strip()}")
            return False
        return True
    except Exception as e:
        log(f"News update exception: {e}")
        return False

def news_get_headlines():
    """Run news_manager.py headlines. Returns parsed JSON or None."""
    try:
        result = subprocess.run(
            [PYTHON_BIN, str(NEWS_MANAGER_SCRIPT), "headlines"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=15
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        log(f"News headlines error: {e}")
    return None

def news_get_next_story():
    """Run news_manager.py next_story. Returns parsed JSON or None."""
    try:
        result = subprocess.run(
            [PYTHON_BIN, str(NEWS_MANAGER_SCRIPT), "next_story"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get('id') and data.get('story'):
                return data
    except Exception as e:
        log(f"News next_story error: {e}")
    return None

def news_mark_presented(story_id):
    """Run news_manager.py mark <id>."""
    try:
        subprocess.run(
            [PYTHON_BIN, str(NEWS_MANAGER_SCRIPT), "mark", story_id],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=10
        )
        log(f"Marked story {story_id} as presented.")
    except Exception as e:
        log(f"News mark error: {e}")

def get_news_instruction():
    """
    Determine the news instruction for this DJ cycle.
    Returns (instruction_text, story_id_to_mark_after_success) or (None, None).
    """
    # Always try to update (respects its own 60-min cache internally)
    news_update()

    news_state = load_news_state()
    now = time.time()
    time_since_headlines = now - news_state.get('last_headlines_at', 0)

    # Top of the hour: full headlines segment
    if time_since_headlines >= NEWS_HEADLINES_INTERVAL:
        headlines_data = news_get_headlines()
        if headlines_data and headlines_data.get('headlines'):
            headline_list = headlines_data['headlines']

            # Build headline text for the DJ
            parts = []
            if headlines_data.get('breaking'):
                parts.append(f"BREAKING NEWS: {headlines_data['breaking']}")

            # Group by type for clarity
            top = [h['headline'] for h in headline_list if h['type'] == 'top']
            regular = [h['headline'] for h in headline_list if h['type'] == 'regular']
            quick = [h['headline'] for h in headline_list if h['type'] == 'quicklink']

            if top:
                parts.append("Top stories: " + "; ".join(top))
            if regular:
                parts.append("Also in the news: " + "; ".join(regular[:5]))
            if quick:
                parts.append("In brief: " + "; ".join(quick[:5]))

            headline_text = "\n".join(parts)

            instruction = (
                f"NEWS SEGMENT: It's time for the hourly news update! Here are the current headlines:\n\n"
                f"{headline_text}\n\n"
                "Please present these headlines to the listeners as a news bulletin in your own words. "
                "Cover the top stories first, then briefly mention a few of the other headlines. "
                "After the news, suggest and introduce a song that fits the overall mood of today's news."
            )

            # Update state — mark headlines as delivered
            news_state['last_headlines_at'] = now
            save_news_state(news_state)

            log(f"News: HEADLINES segment ({len(headline_list)} headlines)")
            return instruction, None

    # Between headlines: try a deep-dive story
    story = news_get_next_story()
    if story:
        instruction = (
            f"NEWS DEEP DIVE: Please present the following news story to the listeners in your own words.\n\n"
            f"Headline: {story['headline']}\n"
            f"Story: {story['story']}\n\n"
            "Summarize this story engagingly for the radio audience, then suggest and introduce "
            "a song that fits the topic or mood of this story."
        )
        log(f"News: DEEP DIVE on '{story['headline'][:50]}...' (id: {story['id']})")
        return instruction, story['id']

    # No news to present
    log("News: nothing new to present this cycle.")
    return None, None

# --- DJ COMMUNICATION ---
def trigger_dj(last_track, listener_input=None, instructions=None):
    """Writes request file, runs DJ brain, reads response."""
    
    # 1. Prepare Request
    request_data = {
        "last_track": last_track,
        "listener_input": listener_input,
        "instructions": instructions
    }
    with open(REQUEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(request_data, f, indent=2)
    log(f"Wrote DJ request. Last Track: {last_track}. Listener Input: {listener_input}. Instructions: {instructions}")

    # 2. Execute DJ Brain
    command = [PYTHON_BIN, str(DJ_BRAIN_SCRIPT)]
    log(f"Executing DJ Brain: {' '.join(command)}")
    
    try:
        # Run DJ brain synchronously, capture output/errors to log
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR) # Ensure it runs from the correct directory
        )
        log(f"DJ Brain finished. STDOUT: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        log(f"DJ Brain FAILED (Code {e.returncode}). Stderr: {e.stderr.strip()}")
        return None

    # 3. Read Response
    response = load_json(RESPONSE_FILE)
    if not response or "error" in response:
        log(f"Failed to get valid response from DJ: {response}")
        return None
        
    return response

def get_next_announcement_slot():
    """Find the next available announcement slot that's old enough to reuse."""
    now = time.time()
    
    # First pass: find a slot that either doesn't exist or is old enough
    for i in range(1, ANNOUNCEMENT_SLOTS + 1):
        mp3_path = BASE_DIR / f"temp_announcement{i}.mp3"
        if not os.path.exists(mp3_path):
            return i
        age = now - os.path.getmtime(mp3_path)
        if age >= ANNOUNCEMENT_MIN_AGE:
            return i
    
    # All slots are too young — pick the oldest one
    oldest_slot = 1
    oldest_age = 0
    for i in range(1, ANNOUNCEMENT_SLOTS + 1):
        mp3_path = BASE_DIR / f"temp_announcement{i}.mp3"
        age = now - os.path.getmtime(mp3_path)
        if age > oldest_age:
            oldest_age = age
            oldest_slot = i
    
    log(f"WARNING: All announcement slots are younger than {ANNOUNCEMENT_MIN_AGE}s. Reusing oldest (slot {oldest_slot}, {int(oldest_age)}s old).")
    return oldest_slot

def generate_announcement_audio(text_content):
    """Generates announcement audio using tts_generate.py with rotating file slots."""
    
    slot = get_next_announcement_slot()
    txt_file = BASE_DIR / f"temp_announcement{slot}.txt"
    mp3_file = BASE_DIR / f"temp_announcement{slot}.mp3"
    
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(text_content)
        
    log(f"Generating announcement audio (slot {slot}): '{text_content[:30]}...'")

    command = [PYTHON_BIN, str(TTS_GENERATOR_SCRIPT), str(txt_file)]
    
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR)
        )
        
        log(f"TTS Generation successful (slot {slot}).")
        return mp3_file
        
    except subprocess.CalledProcessError as e:
        log(f"TTS Generation FAILED (Code {e.returncode}). Stderr: {e.stderr.strip()}")
        return None
    finally:
        # Clean up temporary text file
        if os.path.exists(txt_file):
            os.remove(txt_file)


# --- MAIN LOOP ---
def main():
    log("=" * 60)
    log("DJ Orchestrator starting up.")
    
    last_track_played = None
    
    while True:
        
        listener_input = None # Initialize here
        
        if os.path.exists(SIGNAL_FILE):
            log("Signal detected. Starting DJ cycle.")

            # NEW: Capture listener request ONLY when a DJ cycle is triggered
            listener_input = read_and_clear_listener_request()
            
            # 1. Determine Context (Last track) and GATHER NEWS/WEATHER
            
            # A. Weather Context 
            weather_forecast = get_weather_forecast()
            weather_instruction = None
            weather_is_fresh = False
            if weather_forecast:
                try:
                    age = time.time() - os.path.getmtime(WEATHER_RESULT)
                    weather_is_fresh = (age < 10)
                except Exception:
                    pass

                if weather_is_fresh:
                    weather_instruction = (
                        f"Current weather forecast for Vienna:\n{weather_forecast}\n\n"
                        "It's time for a weather update! Please present the full weather forecast to the listeners in your own words, "
                        "then suggest and introduce a song that fits the current weather mood."
                    )
                    log("Weather segment: FULL forecast mode (fresh scrape)")
                else:
                    weather_instruction = (
                        f"Current weather for Vienna: {weather_forecast}\n"
                        "You may weave weather info naturally into your announcement if it fits, but don't repeat the full forecast."
                    )
                    log("Weather segment: subtle mode (cached)")

            # B. News Segment Check (New Logic)
            news_instruction, news_context_payload = get_news_instruction()
            
            # C. Combine instructions
            combined_instructions = None
            instruction_parts = []
            if weather_instruction:
                instruction_parts.append(weather_instruction)
            if news_instruction:
                instruction_parts.append(news_instruction)
            if instruction_parts:
                combined_instructions = "\n\n---\n\n".join(instruction_parts)

            # D. Prepare request data
            last_track_path = read_last_line(QUEUE_FILE)
            if last_track_path and not last_track_path.endswith(".mp3"): # If it's not a valid file path, treat as unknown
                 last_track_path = None
            
            if last_track_path:
                last_track_name = os.path.basename(last_track_path)
            else:
                last_track_name = "Unknown track (Queue may have been empty)"

            request_data = {
                "last_track": last_track_name,
                "listener_input": listener_input,
                "instructions": combined_instructions
            }
            
            # If we are doing a news deep dive, pass the ID in instructions for post-processing
            mark_id = None
            if news_context_payload and isinstance(news_context_payload, dict) and news_context_payload.get('type') == 'news_deep_dive':
                 mark_id = news_context_payload['story_id']
                 request_data["instructions"] += f"\n__NEWS_ID_TO_MARK__: {mark_id}"

            # --- PHASE 2: DJ EXECUTION & SONG SELECTION ---
            dj_output = None
            success = False
            retry_count = 0
            
            while retry_count < MAX_DJ_ATTEMPTS and not success:
                retry_count += 1
                log(f"--- DJ Attempt {retry_count}/{MAX_DJ_ATTEMPTS} ---")
                
                # 2. Trigger DJ Brain
                dj_output = trigger_dj(request_data["last_track"], request_data["listener_input"], request_data["instructions"])

                if dj_output:
                    suggested_track = dj_output.get("track") # Artist - Title
                    announcement_text = dj_output.get("announcement")
                    
                    if suggested_track and announcement_text:
                        # 3. Find the actual audio file for the suggested track
                        playlist = []
                        try:
                            with open(PLAYLIST_FILE, 'r', encoding='utf-8') as f:
                                playlist = [line.strip() for line in f if line.strip()]
                        except FileNotFoundError:
                            log(f"CRITICAL: Playlist file not found at {PLAYLIST_FILE}")
                            delete_signal()
                            time.sleep(POLL_INTERVAL)
                            continue
                        
                        # --- MUSIC MATCHING LOGIC START ---
                        potential_matches = []
                        
                        cleaned_suggestion = clean_suggestion_for_matching(suggested_track)
                        
                        for p_track in playlist:
                            p_filename = os.path.basename(p_track)
                            p_filename_lower = p_filename.lower()
                            
                            if cleaned_suggestion.lower() in p_filename_lower:
                                is_exact_version_match = suggested_track.lower() in p_filename_lower
                                length_diff = len(p_filename_lower) - len(cleaned_suggestion.lower())
                                potential_matches.append((p_track, p_filename, length_diff, is_exact_version_match))
                        
                        found_track = None
                        if potential_matches:
                            potential_matches.sort(key=lambda x: (not x[3], x[2])) 
                            found_track = potential_matches[0][0]
                        
                        # --- MUSIC MATCHING LOGIC END ---

                        if found_track:
                            # SUCCESS PATH: Track found! Generate audio and queue.
                            log(f"SUCCESS: Found track: {suggested_track}")
                            announcement_audio_path = generate_announcement_audio(announcement_text)

                            if announcement_audio_path:
                                # 5. Append to Queue (Announcement FIRST, then Song)
                                append_to_queue(str(announcement_audio_path))
                                append_to_queue(found_track)
                                last_track_played = found_track
                                
                                # Mark news story as presented if this was a deep dive
                                if mark_id:
                                    news_mark_presented(mark_id)
                                    mark_id = None
                                
                                success = True # Exit inner loop
                            else:
                                log("Skipping DJ turn: Failed to generate announcement audio.")
                        else:
                            # FALLBACK PATH 1: Track not found, add to wishlist, check for alternatives
                            log(f"Track NOT FOUND: {suggested_track}")
                            append_to_wishlist(suggested_track)
                            
                            artist = parse_artist_from_suggestion(suggested_track)
                            
                            if artist:
                                alternatives = find_artist_alternatives(artist, playlist)
                                
                                if alternatives:
                                    # Path A: Alternatives exist -> Reprompt DJ with suggestions
                                    alternative_list = "\n".join(os.path.basename(t) for t in alternatives[:MAX_ARTIST_SUGGESTIONS])
                                    retry_instructions = (f"The track '{suggested_track}' was unavailable. Please select one of the following {len(alternatives)} available tracks by the same artist: {artist}. "
                                                    f"Available tracks include: {alternative_list[:500]}...")
                                    instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                    
                                    log(f"Alternatives found. Setting instructions for next attempt.")
                                    request_data["instructions"] = instructions
                                    # Continue the inner loop (retry_count increments, success remains False)
                                else:
                                    # Path B: No alternatives found -> Handle Listener Request persistence
                                    if request_data["listener_input"]:
                                        retry_instructions = (f"The track '{suggested_track}' by {artist} was requested by a listener but is unavailable in the library. "
                                                        "Please select a track by a COMPLETELY DIFFERENT artist, acknowledging the listener's general request if possible.")
                                        instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                        log(f"Listener request failed for {artist}. Setting instruction to re-prompt DJ.")
                                        request_data["instructions"] = instructions
                                        # success remains False, loop continues to next attempt/retry
                                    else:
                                        # --- CRITICAL FIX APPLIED HERE ---
                                        log(f"No alternatives found for artist: {artist}. Autonomous turn failed. Forcing new artist selection.")
                                        retry_instructions = f"The suggested artist {artist} has no available tracks. Please select a track by a completely different artist entirely."
                                        instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                        request_data["instructions"] = instructions
                                        # success remains False, loop continues to next attempt/retry
                            else:
                                log("Could not parse artist from suggestion. Skipping turn.")
                                success = True # Treat as exhausted turn to avoid infinite loop (artist name is essential)
                    else:
                        log("DJ response incomplete (missing track/announcement). Skipping turn.")
                        success = True # Treat as failed turn
                else:
                    log("DJ cycle triggered, but no valid response.")
                    success = True # Treat as failed turn
            
            # 6. Cleanup signal file (Crucial: done regardless of success/failure)
            delete_signal()

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()