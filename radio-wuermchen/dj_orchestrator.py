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
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        if path.endswith("history.json"):
            return []
        return {}
    except json.JSONDecodeError as e:
        log(f"Error reading JSON file {path}: {e}")
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
def trigger_dj(last_track, instructions=None):
    """Writes request file, runs DJ brain, reads response."""
    
    # 1. Prepare Request
    request_data = {
        "last_track": last_track,
        "listener_input": None, # Future enhancement: check for new listener requests
        "instructions": instructions
    }
    with open(REQUEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(request_data, f, indent=2)
    log(f"Wrote DJ request based on last track: {last_track}. Instructions: {instructions}")

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

def generate_announcement_audio(text_content):
    """Generates announcement audio using tts_generate.py."""
    
    # Create a temporary text file for the TTS script to read
    temp_text_file = BASE_DIR / "temp_announcement.txt"
    with open(temp_text_file, 'w', encoding='utf-8') as f:
        f.write(text_content)
        
    log(f"Generating announcement audio for text: '{text_content[:30]}...'")

    # Run TTS generator. Output path is hardcoded in tts_generate.py to be temp_announcement.mp3
    command = [PYTHON_BIN, str(TTS_GENERATOR_SCRIPT), str(temp_text_file)]
    
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR)
        )
        
        log("TTS Generation successful.")
        # Return path to the hardcoded output file
        return BASE_DIR / "temp_announcement.mp3"
        
    except subprocess.CalledProcessError as e:
        log(f"TTS Generation FAILED (Code {e.returncode}). Stderr: {e.stderr.strip()}")
        return None
    finally:
        # Clean up temporary text file
        if os.path.exists(temp_text_file):
            os.remove(temp_text_file)


# --- MAIN LOOP ---
def main():
    log("=" * 60)
    log("DJ Orchestrator starting up.")
    
    last_track_played = None
    
    while True:
        if os.path.exists(SIGNAL_FILE):
            log("Signal detected. Starting DJ cycle.")
            
            # 1. Determine Context (Last track)
            last_track_path = read_last_line(QUEUE_FILE)
            if last_track_path and not last_track_path.endswith(".mp3"): # If it's not a valid file path, treat as unknown
                 last_track_path = None
            
            if last_track_path:
                last_track_name = os.path.basename(last_track_path)
            else:
                last_track_name = "Unknown track (Queue may have been empty)"
            
            # Initialize request_data here to be available for modification/re-prompting
            request_data = {
                "last_track": last_track_name,
                "listener_input": None,
                "instructions": None
            }
            
            dj_output = None
            success = False
            retry_count = 0
            
            while retry_count < MAX_DJ_ATTEMPTS and not success:
                retry_count += 1
                log(f"--- DJ Attempt {retry_count}/{MAX_DJ_ATTEMPTS} ---")
                
                # 2. Trigger DJ Brain
                dj_output = trigger_dj(request_data["last_track"], request_data["instructions"])

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
                        
                        found_track = None
                        # Simple matching logic (case-insensitive partial match)
                        for p_track in playlist:
                            if suggested_track.lower() in os.path.basename(p_track).lower():
                                found_track = p_track
                                break

                        if found_track:
                            # SUCCESS PATH: Track found! Generate audio and queue.
                            log(f"SUCCESS: Found track: {suggested_track}")
                            announcement_audio_path = generate_announcement_audio(announcement_text)

                            if announcement_audio_path:
                                # 5. Append to Queue (Announcement FIRST, then Song)
                                append_to_queue(str(announcement_audio_path))
                                append_to_queue(found_track)
                                last_track_played = found_track
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
                                    instructions = (f"The track '{suggested_track}' was unavailable. Please select one of the following {len(alternatives)} available tracks by the same artist: {artist}. "
                                                    f"Available tracks include: {alternative_list[:500]}...")
                                    
                                    log(f"Alternatives found. Setting instructions for next attempt.")
                                    request_data["instructions"] = instructions
                                    # Continue the inner loop (retry_count increments, success remains False)
                                else:
                                    # Path B: No alternatives found -> Skip turn
                                    log(f"No alternatives found for artist: {artist}. Skipping turn.")
                                    success = True # Treat as exhausted turn to avoid infinite loop
                            else:
                                log("Could not parse artist from suggestion. Skipping turn.")
                                success = True # Treat as exhausted turn
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