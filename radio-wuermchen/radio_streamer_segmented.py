# Dynamic Segment Streamer (Agent-Driven Protocol - Direct Icecast Stream - FAST RECONNECT MODE)

import subprocess
import time
import os
import random
import re
import json
from datetime import datetime
import sys

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PLAYLIST_FILE = os.path.join(SCRIPT_DIR, "music.playlist")
FFMPEG_BIN = "C:/msys64/mingw64/bin/ffmpeg.exe"
CONCAT_LIST_PATH = os.path.join(SCRIPT_DIR, "temp_concat.txt") 
SILENT_ANNOUNCER = os.path.join(SCRIPT_DIR, "cache", "silent_announcer.mp3") 

# Agent Communication Files
DJ_REQUEST_PATH = os.path.join(SCRIPT_DIR, "dj_request.json")
DJ_RESPONSE_PATH = os.path.join(SCRIPT_DIR, "dj_response.json")
WISHLIST_PATH = os.path.join(SCRIPT_DIR, "wishlist.txt")
DJ_LOG_PATH = os.path.join(SCRIPT_DIR, "dj_log.jsonl") 

TIMEOUT_SECONDS = 10 
ANNOUNCER_TIMEOUT = 1 

# --- ICECAST CONFIGURATION ---
# Using the Segment Reconnect model (FFmpeg closes after each song)
ICECAST_URL = "icecast://source:hackme@localhost:8000/stream"


# --- UTILITIES (REINCLUDED) ---

def log_event(event_type, **kwargs):
    log_entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], 
        "type": event_type,
        **kwargs
    }
    try:
        with open(DJ_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except IOError as e:
        sys.stderr.write(f"Error writing to log file: {e}\n")


def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            time.sleep(0.1)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return None
    return None

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def get_all_tracks(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tracks = [line.strip() for line in f if line.strip()]
        return tracks
    except FileNotFoundError:
        return []

def get_artist_title(track_path):
    base_name = os.path.basename(track_path)
    name_no_ext = os.path.splitext(os.path.basename(track_path))[0].strip()
    match = re.match(r'^(.*?)\s*-\s*(.*)$', name_no_ext) 
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "Unknown Artist", name_no_ext

def get_title_from_suggestion(suggestion):
    base_name = os.path.splitext(os.path.basename(suggestion.strip()))[0] 
    match = re.match(r'^(.*?)\s*-\s*(.*)$', base_name)
    if match:
        artist_title = f"{match.group(1).strip()} - {match.group(2).strip()}"
    else:
        artist_title = base_name 
        
    normalized = re.sub(r'[^\w\s-]', '', artist_title).lower()
    return normalized


def find_track_path(suggestion, all_tracks):
    suggestion_norm = get_title_from_suggestion(suggestion)
    for track_path in all_tracks:
        track_name_norm = get_title_from_suggestion(os.path.basename(track_path))
        if track_name_norm == suggestion_norm:
            log_event("track_match", status="found_exact", suggestion=suggestion, track_path=track_path)
            return track_path

    log_event("track_match", status="not_found", suggestion=suggestion)
    return None

def add_to_wishlist(suggestion):
    try:
        with open(WISHLIST_PATH, 'a', encoding='utf-8') as f:
            f.write(f"{suggestion}\n")
        log_event("wishlist", suggestion=suggestion, status="added")
    except IOError as e:
        sys.stderr.write(f"Error writing to wishlist: {e}\n")


def prepare_segment(last_track_path, all_tracks):
    """
    FOR DEBUGGING: Skips LLM calls and forces a random track immediately.
    """
    
    # Force immediate random track selection
    next_track_path = random.choice(all_tracks)
    announcer_file = SILENT_ANNOUNCER if os.path.exists(SILENT_ANNOUNCER) else None
    
    # Logging the skip
    log_event("debug_skip", message="Skipped LLM call for fast debugging", next_track=next_track_path)
    
    segment_files = []
    if announcer_file:
        segment_files.append(announcer_file)
    
    segment_files.append(next_track_path) 
    
    log_event("segment_prepared", track=next_track_path, announcer=announcer_file)
    
    # This function now completes in milliseconds, allowing fast testing
    return {
        "files": segment_files,
        "track_played": next_track_path
    }


# --- MAIN STREAMING LOGIC ---

def stream_radio():
    log_event("script_start", status="initialized_fast_reconnect")
    sys.stderr.write("Starting Agent-Driven Direct Icecast Streamer (FAST RECONNECT MODE)...\n")
    
    os.makedirs(os.path.join(SCRIPT_DIR, "cache"), exist_ok=True)
    all_tracks = get_all_tracks(PLAYLIST_FILE)
    if not all_tracks:
        sys.stderr.write("Playlist is empty. Exiting.\n")
        return

    current_stream_process = None
    last_track_path = None
    
    # 1. Pre-Prepare the first segment before the main loop starts
    sys.stderr.write("Pre-preparing first segment...\n")
    prepared_segment = prepare_segment(last_track_path, all_tracks)
    
    while True:
        try:
            # --- Wait for Previous Stream to End ---
            if current_stream_process:
                sys.stderr.write(f"Waiting for current track to finish (PID: {current_stream_process.pid})...\n")
                current_stream_process.wait() 
                log_event("stream_process_wait_complete", pid=current_stream_process.pid)
                
                if current_stream_process.returncode != 0:
                    log_event("stream_end", status="non_zero_exit", code=current_stream_process.returncode, track_played=last_track_path)
                    sys.stderr.write(f"Warning: FFmpeg process exited with code {current_stream_process.returncode}. Attempting to proceed with next segment.\n")


            # --- Phase 4: Stream the PREPARED Segment (Start Non-Blocking) ---
            segment_to_stream = prepared_segment
            last_track_path = segment_to_stream["track_played"]
            segment_files = segment_to_stream["files"]
            
            with open(CONCAT_LIST_PATH, 'w', encoding='utf-8') as f:
                for file in segment_files:
                    safe_file = file.replace('\\', '/').replace("'", r"'\''")
                    f.write(f"file '{safe_file}'\n")

            # FFmpeg command (using -re to stream at native rate)
            ffmpeg_command = [
                FFMPEG_BIN,
                "-f", "concat",
                "-safe", "0", 
                "-re", 
                "-i", CONCAT_LIST_PATH,
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                "-f", "mp3", 
                "-content_type", "audio/mpeg",
                ICECAST_URL 
            ]

            log_event("stream_start", files=[os.path.basename(f) for f in segment_files])
            sys.stderr.write(f"\n---> Starting Stream Segment (Target: {os.path.basename(last_track_path)})...\n")
            
            # Note: stdout/stderr not piped, so FFmpeg prints its own messages
            current_stream_process = subprocess.Popen(ffmpeg_command)
            log_event("stream_process_started", pid=current_stream_process.pid, track_played=last_track_path)
            
            
            # --- Phase 5: Prepare the NEXT Segment (During Current Stream) ---
            # This is instantaneous now.
            prepared_segment = prepare_segment(last_track_path, all_tracks)

            
        except subprocess.CalledProcessError as e:
            error_output = e.stderr.decode('utf-8', errors='ignore') if e.stderr is not None else "No stderr captured."
            log_event("stream_end", status="crash", error=f"Code {e.returncode}", ffmpeg_output=error_output)
            sys.stderr.write(f"FFmpeg Segment Error (Code {e.returncode}): Segment encoding failed or Icecast disconnected. Attempting restart.\n")
            sys.stderr.write(f"FFmpeg Error Output: {error_output}\n")
            time.sleep(1) 
            
        except Exception as e:
            log_event("critical_error", error=str(e))
            sys.stderr.write(f"CRITICAL LOOP EXCEPTION: Script crashed during processing: {e}\n")
            time.sleep(5) 
            
if __name__ == "__main__":
    stream_radio()