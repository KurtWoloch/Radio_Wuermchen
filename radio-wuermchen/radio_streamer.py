# Dynamic Segment Streamer (FILE POLLING DJ Mode - Pipe Writer)

import subprocess
import time
import os
import sys
import json
from datetime import datetime
import re
import random

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PLAYLIST_FILE = os.path.join(SCRIPT_DIR, "music.playlist")
FFMPEG_BIN = "C:/msys64/mingw64/bin/ffmpeg.exe"
CONCAT_LIST_PATH = os.path.join(SCRIPT_DIR, "temp_concat.txt") 
SILENT_ANNOUNCER = os.path.join(SCRIPT_DIR, "cache", "silent_announcer.mp3") 

# --- DJ AGENT COMMUNICATION (File Polling) ---
DJ_REQUEST_PATH = os.path.join(SCRIPT_DIR, "dj_request.json")
DJ_RESPONSE_PATH = os.path.join(SCRIPT_DIR, "dj_response.json")
DJ_LOG_PATH = os.path.join(SCRIPT_DIR, "dj_log.jsonl") 

TIMEOUT_SECONDS = 180 # Time to wait for agent response file

# --- ICECAST CONFIGURATION ---
ICECAST_URL = "icecast://source:hackme@localhost:8000/stream"

# --- UTILITIES (Full functions must be here) ---

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
        log_event("critical_error", error=f"Playlist file not found at {file_path}")
        print(f"CRITICAL: Playlist file not found at {file_path}", file=sys.stderr)
        return []

def get_artist_title(track_path):
    base_name = os.path.basename(track_path)
    name_no_ext = os.path.splitext(os.path.basename(track_path))[0].strip()
    match = re.match(r'^(.*?)\s*-\s*(.*)$', name_no_ext) 
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "Unknown Artist", name_no_ext

def track_to_display(track_path):
    artist, title = get_artist_title(track_path)
    return f"{artist} - {title}"

def track_to_path(display_name, all_tracks):
    display_name = display_name.strip()
    for track_path in all_tracks:
        if track_to_display(track_path) == display_name:
            return track_path
    return None


# --- DJ COMMUNICATION LOGIC (File Polling) ---

def communicate_with_dj(last_track_path, all_tracks):
    """
    Writes request to file and polls for structured JSON response file.
    """
    
    # 1. Prepare the request
    last_track_display = track_to_display(last_track_path) if last_track_path else "None"
    
    request_data = {
        "mode": "select_track_and_announce",
        "last_track": last_track_display,
        "timestamp": time.time()
    }
    
    # 2. Write request file
    log_event("dj_request_written", last_track=last_track_display)
    save_json(DJ_REQUEST_PATH, request_data)
    
    # 3. Poll for response file
    response_data = None
    start_time = time.time()
    
    while time.time() - start_time < TIMEOUT_SECONDS: 
        time.sleep(0.5) 
        response_data = load_json(DJ_RESPONSE_PATH)
        if response_data and response_data.get("request_timestamp") == request_data["timestamp"]:
            os.remove(DJ_RESPONSE_PATH) 
            break

    if not response_data:
        log_event("timeout", mode="file_polling", msg="DJ Agent failed to respond within timeout. Falling back to random.")
        print("CRITICAL: DJ Agent timeout, falling back to random.", file=sys.stderr)
        
        # Fallback to instantaneous random selection
        next_track_path = random.choice(all_tracks)
        announcer_file = SILENT_ANNOUNCER if os.path.exists(SILENT_ANNOUNCER) else None
        
        return {
            "files": [announcer_file, next_track_path],
            "track_played": next_track_path,
            "action": "STREAM"
        }
    
    # 4. Process valid response (adapted to the agent's actual key names)
    track_file_name = response_data.get("track_file")
    tts_media_path = response_data.get("announcer_mp3_path")
    
    next_track_path = None
    
    # Find the full path for the given filename from the playlist
    if track_file_name:
        for track_path in all_tracks:
            if os.path.basename(track_path) == track_file_name:
                next_track_path = track_path
                break

    if not next_track_path:
        log_event("error", error="Agent suggested non-existent track (or missing key 'track_file')", suggestion=track_file_name)
        next_track_path = random.choice(all_tracks)
        # Use a silent announcement for the fallback track
        tts_media_path = SILENT_ANNOUNCER if os.path.exists(SILENT_ANNOUNCER) else None

    segment_files = []
    if tts_media_path and os.path.exists(tts_media_path):
        segment_files.append(tts_media_path)
    
    segment_files.append(next_track_path) 
    
    log_event("segment_prepared", track=next_track_path, announcer=tts_media_path)
    
    return {
        "files": segment_files,
        "track_played": next_track_path,
        "action": "STREAM"
    }


# --- MAIN STREAMING LOGIC (PIPE WRITER) ---

def stream_radio_pipe_writer():
    log_event("script_start", status="initialized_pipe_writer_file_polling")
    
    os.makedirs(os.path.join(SCRIPT_DIR, "cache"), exist_ok=True)
    all_tracks = get_all_tracks(PLAYLIST_FILE)
    if not all_tracks:
        print("CRITICAL: Playlist is empty. Exiting.", file=sys.stderr)
        return

    last_track_path = None
    
    # 1. Pre-Prepare the first segment (writes request file)
    prepared_segment = communicate_with_dj(last_track_path, all_tracks)
    
    while True:
        try:
            if prepared_segment.get("action") != "STREAM":
                log_event("shutdown", reason="DJ communication failed/requested shutdown.")
                print("Exiting stream loop via DJ request/failure.", file=sys.stderr)
                break
                
            # --- Get the Segment to Stream ---
            segment_to_stream = prepared_segment
            last_track_path = segment_to_stream["track_played"]
            segment_files = segment_to_stream["files"]
            
            # --- Phase 4: Output the Segment to STDOUT (The Pipe) ---
            
            concat_input = "concat:" + "|".join(segment_files)
            
            ffmpeg_command = [
                FFMPEG_BIN,
                "-loglevel", "quiet", 
                "-i", concat_input,
                "-c", "copy",
                "-f", "mp3", 
                "pipe:1"               # Output to STDOUT for the pipe
            ]

            log_event("stream_segment_start_pipe", files=[os.path.basename(f) for f in segment_files])
            
            subprocess.run(ffmpeg_command, 
                           stdout=sys.stdout,
                           stderr=sys.stderr,
                           check=True)
            
            log_event("stream_segment_end_pipe", status="written_to_pipe", track_played=last_track_path)
            
            # --- Phase 5: Prepare the NEXT Segment (File Polling) ---
            prepared_segment = communicate_with_dj(last_track_path, all_tracks)

            
        except subprocess.CalledProcessError as e:
            log_event("ffmpeg_error", error=f"FFmpeg Pipe Writer Error (Code {e.returncode}): Segment concatenation/pipe write failed.")
            print(f"FFmpeg Pipe Writer Error (Code {e.returncode}). Trying next segment.", file=sys.stderr)
            prepared_segment = communicate_with_dj(last_track_path, all_tracks) 
            time.sleep(1)
            
        except Exception as e:
            log_event("critical_error", error=str(e))
            print(f"CRITICAL LOOP EXCEPTION: Script crashed during processing: {e}", file=sys.stderr)
            time.sleep(5) 

if __name__ == "__main__":
    stream_radio_pipe_writer()