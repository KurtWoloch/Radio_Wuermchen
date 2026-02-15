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

# --- IMPORTS FROM NEW MANAGERS ---
from weather_manager import get_weather_forecast, WEATHER_RESULT
from tts_manager import generate_announcement_audio
from news_scheduler import get_news_instruction, news_mark_presented

# --- CONFIGURATION ---
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = BASE_DIR / "queue.txt"
SIGNAL_FILE = BASE_DIR / "queue_low.signal"
REQUEST_FILE = BASE_DIR / "dj_request.json"
RESPONSE_FILE = BASE_DIR / "dj_response.json"
PLAYLIST_FILE = BASE_DIR / "music.playlist"
DJ_BRAIN_SCRIPT = BASE_DIR / "dj_brain.py"
LOG_FILE = BASE_DIR / "orchestrator.log"
WISHLIST_FILE = BASE_DIR / "Wishlist.txt"
LISTENER_REQUEST_FILE = BASE_DIR / "listener_request.txt"
SUGGESTION_POOL_FILE = BASE_DIR / "suggestion_pool.txt"
HISTORY_FILE = BASE_DIR / "dj_history.json" # NEW: Added History file constant

PYTHON_BIN = "C:\\Program Files\\Python311\\python.exe"
POLL_INTERVAL = 3  # seconds between checks
MAX_ARTIST_SUGGESTIONS = 50 # Maximum tracks to offer the DJ if suggestion fails
MAX_POOL_SUGGESTIONS = 50   # Maximum tracks to offer from the suggestion pool
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
    with open(str(path), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def read_last_line(path):
    """Reads the last non-empty line from a file."""
    try:
        with open(str(path), 'rb') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            if file_size == 0:
                return None
            
            chunk_size = 1024
            buffer = b''
            while f.tell() > 0:
                read_size = min(chunk_size, f.tell())
                f.seek(-read_size, os.SEEK_CUR)
                chunk = f.read(read_size)
                buffer = chunk + buffer
                
                if b'\n' in chunk:
                    return buffer.split(b'\n')[-2].decode('utf-8').strip()
                
                if f.tell() == 0:
                    return buffer.decode('utf-8').strip()

            return buffer.decode('utf-8').strip()
    except Exception as e:
        log(f"Error reading last line from {path}: {e}")
        return None

def delete_signal():
    """Delete the signal file."""
    try:
        os.remove(str(SIGNAL_FILE))
        log("Signal file deleted.")
    except FileNotFoundError:
        pass

def read_and_clear_listener_request():
    """Read listener request from file and delete the file."""
    try:
        with open(str(LISTENER_REQUEST_FILE), 'r', encoding='utf-8') as f:
            request = f.read().strip()
        os.remove(str(LISTENER_REQUEST_FILE))
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
    with open(str(QUEUE_FILE), 'a', encoding='utf-8') as f:
        f.write(track_path + '\n')
    log(f"Appended to queue: {os.path.basename(track_path)}")

def append_to_wishlist(track_suggestion):
    """Append a track suggestion to the Wishlist file."""
    with open(str(WISHLIST_FILE), 'a', encoding='utf-8') as f:
        f.write(track_suggestion + '\n')
    log(f"Appended to wishlist: {track_suggestion}")

# --- SUGGESTION POOL ---
def read_suggestion_pool():
    """Read the suggestion pool file. Returns list of 'Artist - Track' strings."""
    try:
        with open(str(SUGGESTION_POOL_FILE), 'r', encoding='latin-1') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        return lines
    except FileNotFoundError:
        return []

def remove_from_suggestion_pool(track_name):
    """Remove a track from the suggestion pool (by matching Artist - Track name in filename)."""
    pool = read_suggestion_pool()
    if not pool:
        return
    
    track_lower = track_name.lower()
    new_pool = []
    removed = False
    for line in pool:
        if not removed and line.lower() in track_lower:
            log(f"Removed from suggestion pool: {line}")
            removed = True
        else:
            new_pool.append(line)
    
    if removed:
        with open(str(SUGGESTION_POOL_FILE), 'w', encoding='latin-1') as f:
            for line in new_pool:
                f.write(line + '\n')

def get_pool_suggestions(max_count=MAX_POOL_SUGGESTIONS):
    """Get the top N suggestions from the pool."""
    pool = read_suggestion_pool()
    return pool[:max_count]

# --- ARTIST MATCHING ---
def parse_artist_from_suggestion(suggestion):
    """Extracts the artist part from an 'Artist - Title' string."""
    if " - " in suggestion:
        return suggestion.split(" - ", 1)[0].strip()
    return None

def clean_suggestion_for_matching(suggestion):
    """Strips versioning/subtitles from the suggested track name for better matching."""
    cleaned = re.sub(r'\s*\(.*\)\s*', ' ', suggestion).strip()
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

# --- DJ COMMUNICATION ---
def trigger_dj(last_track, listener_input=None, instructions=None):
    """Writes request file, runs DJ brain, reads response."""
    
    request_data = {
        "last_track": last_track,
        "listener_input": listener_input,
        "instructions": instructions
    }
    with open(str(REQUEST_FILE), 'w', encoding='utf-8') as f:
        json.dump(request_data, f, indent=2)
    log(f"Wrote DJ request. Last Track: {last_track}. Listener Input: {listener_input}. Instructions: {instructions}")

    command = [PYTHON_BIN, str(DJ_BRAIN_SCRIPT)]
    log(f"Executing DJ Brain: {' '.join(command)}")
    
    try:
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, cwd=str(BASE_DIR)
        )
        log(f"DJ Brain finished. STDOUT: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        log(f"DJ Brain FAILED (Code {e.returncode}). Stderr: {e.stderr.strip()}")
        return None

    response = load_json(RESPONSE_FILE)
    if not response or "error" in response:
        log(f"Failed to get valid response from DJ: {response}")
        return None
        
    return response


# --- MAIN LOOP ---
def main():
    log("=" * 60)
    log("DJ Orchestrator starting up.")
    
    last_track_played = None
    
    while True:
        
        listener_input = None
        
        if os.path.exists(SIGNAL_FILE):
            log("Signal detected. Starting DJ cycle.")

            listener_input = read_and_clear_listener_request()
            
            # --- PHASE 1: CONTEXT GATHERING ---
            
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

            # B. News Segment Check
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
            if last_track_path and not last_track_path.endswith(".mp3"):
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
            
            # Track news deep dive for post-processing
            mark_id = None
            if news_context_payload and isinstance(news_context_payload, str):
                 mark_id = news_context_payload
                 log(f"Deep dive story queued for marking after success: {mark_id}")
                 request_data["instructions"] += f"\n__NEWS_ID_TO_MARK__: {mark_id}"
            
            # --- PHASE 2: DJ EXECUTION & SONG SELECTION ---
            dj_output = None
            success = False
            retry_count = 0
            
            while retry_count < MAX_DJ_ATTEMPTS and not success:
                retry_count += 1
                log(f"--- DJ Attempt {retry_count}/{MAX_DJ_ATTEMPTS} ---")
                
                dj_output = trigger_dj(request_data["last_track"], request_data["listener_input"], request_data["instructions"])

                if dj_output:
                    suggested_track = dj_output.get("track")
                    announcement_text = dj_output.get("announcement")
                    
                    if suggested_track and announcement_text:
                        # Load playlist
                        playlist = []
                        try:
                            with open(str(PLAYLIST_FILE), 'r', encoding='utf-8') as f:
                                playlist = [line.strip() for line in f if line.strip()]
                        except FileNotFoundError:
                            log(f"CRITICAL: Playlist file not found at {PLAYLIST_FILE}")
                            delete_signal()
                            time.sleep(POLL_INTERVAL)
                            continue
                        
                        # --- HISTORY CHECK & VALIDATION START ---
                        
                        history = load_json(str(HISTORY_FILE))
                        recent_tracks = [entry["track"].lower() for entry in history if "track" in entry]
                        
                        if suggested_track.lower() in recent_tracks:
                            log(f"DJ Suggestion REJECTED: '{suggested_track}' is in recent history.")
                            found_track = None 
                        else:
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
                                append_to_queue(str(announcement_audio_path))
                            else:
                                log("TTS failed — queueing track without announcement.")
                            
                            append_to_queue(found_track)
                            last_track_played = found_track
                            
                            # Remove from suggestion pool if it came from there
                            remove_from_suggestion_pool(os.path.basename(found_track))
                            
                            # Mark news story as presented if this was a deep dive
                            if mark_id:
                                news_mark_presented(mark_id)
                                mark_id = None
                            
                            success = True
                        else:
                            # FALLBACK PATH 1: Track not found (or rejected by history)
                            log(f"Track NOT FOUND or REJECTED: {suggested_track}")
                            append_to_wishlist(suggested_track)
                            
                            # --- SUGGESTION POOL FALLBACK (Priority 1) ---
                            pool_suggestions = get_pool_suggestions()
                            if pool_suggestions:
                                pool_list = "\n".join(pool_suggestions)
                                retry_instructions = (
                                    f"The track '{suggested_track}' was unavailable. "
                                    f"Please select one of the following recommended tracks instead. "
                                    f"These are listed from most recommended to least recommended:\n{pool_list}"
                                )
                                instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                log(f"Offering {len(pool_suggestions)} tracks from suggestion pool.")
                                request_data["instructions"] = instructions
                            else:
                                # --- ARTIST ALTERNATIVES FALLBACK (Priority 2) ---
                                artist = parse_artist_from_suggestion(suggested_track)
                                
                                if artist:
                                    alternatives = find_artist_alternatives(artist, playlist)
                                    
                                    if alternatives:
                                        alternative_list = "\n".join(os.path.basename(t) for t in alternatives[:MAX_ARTIST_SUGGESTIONS])
                                        retry_instructions = (
                                            f"The track '{suggested_track}' was unavailable. "
                                            f"Please select one of the following {len(alternatives)} available tracks by the same artist: {artist}. "
                                            f"Available tracks include: {alternative_list[:500]}..."
                                        )
                                        instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                        log(f"Alternatives found. Setting instructions for next attempt.")
                                        request_data["instructions"] = instructions
                                    else:
                                        if request_data["listener_input"]:
                                            retry_instructions = (
                                                f"The track '{suggested_track}' by {artist} was requested by a listener but is unavailable in the library. "
                                                "Please select a track by a COMPLETELY DIFFERENT artist, acknowledging the listener's general request if possible."
                                            )
                                            instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                            log(f"Listener request failed for {artist}. Setting instruction to re-prompt DJ.")
                                            request_data["instructions"] = instructions
                                        else:
                                            log(f"No alternatives found for artist: {artist}. Forcing new artist selection.")
                                            retry_instructions = f"The suggested artist {artist} has no available tracks. Please select a track by a completely different artist entirely."
                                            instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                            request_data["instructions"] = instructions
                                else:
                                    log("Could not parse artist from suggestion. Skipping turn.")
                                    success = True
                    else:
                        log("DJ response incomplete (missing track/announcement). Skipping turn.")
                        success = True
                else:
                    log("DJ cycle triggered, but no valid response.")
                    success = True
            
            # 6. Cleanup signal file (Crucial: done regardless of success/failure)
            delete_signal()

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()