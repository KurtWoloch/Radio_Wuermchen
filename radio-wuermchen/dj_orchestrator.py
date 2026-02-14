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

PYTHON_BIN = "C:\\Program Files\\Python311\\python.exe"
POLL_INTERVAL = 3  # seconds between checks

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

# --- DJ COMMUNICATION ---
def trigger_dj(last_track):
    """Writes request file, runs DJ brain, reads response."""
    
    # 1. Prepare Request
    request_data = {
        "last_track": last_track,
        "listener_input": None, # Future enhancement: check for new listener requests
        "instructions": None
    }
    with open(REQUEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(request_data, f, indent=2)
    log(f"Wrote DJ request based on last track: {last_track}")

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
            
            # 2. Trigger DJ Brain
            dj_output = trigger_dj(last_track_name)

            if dj_output:
                suggested_track_path = dj_output.get("track") # This is Artist - Title, not a file path
                announcement_text = dj_output.get("announcement")
                
                if suggested_track_path and announcement_text:
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
                        if suggested_track_path.lower() in os.path.basename(p_track).lower():
                            found_track = p_track
                            break

                    if found_track:
                        # 4. Generate Announcement Audio
                        announcement_audio_path = generate_announcement_audio(announcement_text)

                        if announcement_audio_path:
                            # 5. Append to Queue (Announcement FIRST, then Song)
                            append_to_queue(str(announcement_audio_path))
                            append_to_queue(found_track)
                            last_track_played = found_track
                        else:
                            log("Skipping DJ turn: Failed to generate announcement audio.")
                    else:
                        log(f"DJ suggested track not found in playlist: {suggested_track_path}")
                        log(f"DJ suggestion JSON: {json.dumps(dj_output)}")
                        # If track not found, we must re-trigger the DJ immediately on next cycle
                        # to ask for a new suggestion, but first, delete signal to stop current cycle.
                        delete_signal() 
                else:
                    log("DJ response incomplete. Skipping turn.")
            else:
                log("DJ cycle triggered, but no valid response or track found.")

            # 6. Cleanup signal file (Crucial: done regardless of success/failure)
            delete_signal()

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()