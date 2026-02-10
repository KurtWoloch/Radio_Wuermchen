# Dynamic Segment Streamer (Agent-Driven Protocol - Pipe-Writer Mode)

import subprocess
import time
import os
import random
import re
import json
from itertools import cycle
from datetime import datetime

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PLAYLIST_FILE = os.path.join(SCRIPT_DIR, "music.playlist")
FFMPEG_BIN = "C:/msys64/mingw64/bin/ffmpeg.exe"
CONCAT_LIST_PATH = os.path.join(SCRIPT_DIR, "temp_concat.txt") 

# Agent Communication Files
DJ_REQUEST_PATH = os.path.join(SCRIPT_DIR, "dj_request.json")
DJ_RESPONSE_PATH = os.path.join(SCRIPT_DIR, "dj_response.json")
WISHLIST_PATH = os.path.join(SCRIPT_DIR, "wishlist.txt")
DJ_LOG_PATH = os.path.join(SCRIPT_DIR, "dj_log.jsonl") 

TIMEOUT_SECONDS = 10 # CRITICAL FIX: Reduced timeout for Cron job latency


# --- UTILITIES ---

def log_event(event_type, **kwargs):
    """Appends a structured log entry to the dj_log.jsonl file."""
    log_entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], 
        "type": event_type,
        **kwargs
    }
    try:
        with open(DJ_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except IOError as e:
        print(f"Error writing to log file: {e}")


def load_json(path):
    # ... (omitted for brevity, content is unchanged) ...
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            time.sleep(0.1)
            return load_json(path)
    return None

def save_json(path, data):
    # ... (omitted for brevity, content is unchanged) ...
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    print(f"File written: {os.path.basename(path)}")


def get_all_tracks(file_path):
    # ... (omitted for brevity, content is unchanged) ...
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tracks = [line.strip() for line in f if line.strip()]
        return tracks
    except FileNotFoundError:
        print(f"Error: Playlist file not found at {file_path}")
        return []

def get_artist_title(track_path):
    # ... (omitted for brevity, content is unchanged) ...
    base_name = os.path.basename(track_path)
    name_no_ext = os.path.splitext(os.path.basename(track_path))[0].strip()
    match = re.match(r'^(.*?)\s*-\s*(.*)$', name_no_ext) 
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "Unknown Artist", name_no_ext

def get_title_from_suggestion(suggestion):
    """
    Extracts Artist - Title from any suggestion (path, filename, or text) 
    and normalizes it for comparison.
    """
    base_name = os.path.splitext(os.path.basename(suggestion.strip()))[0] 
    match = re.match(r'^(.*?)\s*-\s*(.*)$', base_name)
    if match:
        artist_title = f"{match.group(1).strip()} - {match.group(2).strip()}"
    else:
        artist_title = base_name 
        
    normalized = re.sub(r'[^\w\s-]', '', artist_title).lower()
    return normalized


def find_track_path(suggestion, all_tracks):
    """
    Searches the playlist for the suggested track, supporting exact and wildcard matches.
    Now performs case-insensitive matching on the 'Artist - Title' part of the filename.
    """
    suggestion_norm = get_title_from_suggestion(suggestion)
    
    # 1. Exact Match (Case-insensitive)
    for track_path in all_tracks:
        track_name_norm = get_title_from_suggestion(os.path.basename(track_path))
        if track_name_norm == suggestion_norm:
            log_event("track_match", status="found_exact", suggestion=suggestion, track_path=track_path)
            return track_path

    # 2. Wildcard Match (e.g., 'AVICII * - Wake me up')
    if '*' in suggestion:
        pattern = re.escape(suggestion).replace(r'\*', '.*?')
        regex = re.compile(pattern, re.IGNORECASE) 
        
        for track_path in all_tracks:
            track_name = os.path.splitext(os.path.basename(track_path))[0].strip()
            if regex.search(track_name):
                log_event("track_match", status="found_wildcard", suggestion=suggestion, track_name=track_name, track_path=track_path)
                return track_path

    log_event("track_match", status="not_found", suggestion=suggestion)
    return None

def add_to_wishlist(suggestion):
    """Appends a track suggestion to the wishlist file."""
    try:
        with open(WISHLIST_PATH, 'a', encoding='utf-8') as f:
            f.write(f"{suggestion}\n")
        log_event("wishlist", suggestion=suggestion, status="added")
    except IOError as e:
        print(f"Error writing to wishlist: {e}")

# --- MAIN STREAMING LOGIC ---

def stream_radio():
    log_event("script_start", status="initialized")
    print("Starting Agent-Driven Pipe-Writer Streamer...")
    
    os.makedirs(os.path.join(SCRIPT_DIR, "cache"), exist_ok=True)
    all_tracks = get_all_tracks(PLAYLIST_FILE)
    if not all_tracks:
        print("Playlist is empty. Exiting.")
        return

    last_track_path = None
    
    while True:
        next_track_path = None

        try:
            # --- PHASE 1: Determine Next Track (Request Agent A) ---
            
            last_track_info = "None"
            if last_track_path:
                artist, title = get_artist_title(last_track_path)
                last_track_info = f"{artist} - {title}"
                
            request_data = {
                "mode": "select_track",
                "last_track": last_track_info,
                "available_tracks": None, 
                "timestamp": time.time()
            }
            
            log_event("request_start", mode="select_track", last_track=last_track_info)
            save_json(DJ_REQUEST_PATH, request_data)
            
            # 2. Wait for Agent Response
            response_data = None
            start_time = time.time()
            
            while time.time() - start_time < TIMEOUT_SECONDS: 
                time.sleep(0.5) 
                response_data = load_json(DJ_RESPONSE_PATH)
                if response_data and response_data.get("request_timestamp") == request_data["timestamp"]:
                    log_event("response_received", mode="select_track", duration=time.time() - start_time)
                    os.remove(DJ_RESPONSE_PATH) 
                    break
            
            if not response_data:
                log_event("timeout", mode="select_track")
                next_track_path = random.choice(all_tracks)
                
            else:
                suggested_track = response_data.get("suggested_track")
                if not suggested_track:
                    log_event("error", error="missing_suggested_track", mode="select_track")
                    next_track_path = random.choice(all_tracks)
                else:
                    # --- PHASE 2: Validation and Fallback ---
                    next_track_path = find_track_path(suggested_track, all_tracks)
                    
                    if not next_track_path:
                        # Track not found - Initiate Fallback
                        add_to_wishlist(suggested_track)
                        
                        safe_options = random.sample(all_tracks, min(5, len(all_tracks)))
                        
                        fallback_request = {
                            "mode": "suggest_options",
                            "last_track": last_track_info,
                            "available_tracks": [get_artist_title(t) for t in safe_options],
                            "timestamp": time.time()
                        }

                        log_event("request_start", mode="suggest_options", options=fallback_request['available_tracks'])
                        save_json(DJ_REQUEST_PATH, fallback_request)
                        
                        # Wait for the fallback response
                        fallback_response_data = None
                        start_time = time.time()
                        while time.time() - start_time < TIMEOUT_SECONDS:
                            time.sleep(0.5)
                            fallback_response_data = load_json(DJ_RESPONSE_PATH)
                            if fallback_response_data and fallback_response_data.get("request_timestamp") == fallback_request["timestamp"]:
                                log_event("response_received", mode="suggest_options", duration=time.time() - start_time)
                                os.remove(DJ_RESPONSE_PATH)
                                break
                        
                        if fallback_response_data:
                            final_suggestion = fallback_response_data.get("suggested_track")
                            if final_suggestion:
                                next_track_path = find_track_path(final_suggestion, all_tracks)
                                if not next_track_path:
                                    log_event("error", error="fallback_mismatch", suggestion=final_suggestion)
                                    next_track_path = random.choice(all_tracks)
                                else:
                                    log_event("track_selection", status="fallback_success", track_path=next_track_path)
                            else:
                                log_event("error", error="fallback_missing_suggestion")
                                next_track_path = random.choice(all_tracks)
                        else:
                            log_event("timeout", mode="suggest_options")
                            next_track_path = random.choice(all_tracks)
                    else:
                        log_event("track_selection", status="direct_success", track_path=next_track_path)
            
            
            # --- PHASE 3: Generate Announcement (Request Agent B) ---
            next_artist, next_title = get_artist_title(next_track_path)
            
            announcement_request = {
                "mode": "generate_announcement",
                "last_track": last_track_info, 
                "next_track": f"{next_artist} - {next_title}",
                "cache_path": os.path.join(SCRIPT_DIR, "cache"),
                "timestamp": time.time()
            }
            
            log_event("request_start", mode="generate_announcement", next_track=announcement_request['next_track'])
            save_json(DJ_REQUEST_PATH, announcement_request)
            
            # Wait for Agent B to place the final MP3 file and write the response
            announcer_file = None
            start_time = time.time()
            ANNOUNCER_TIMEOUT = 120 
            
            while time.time() - start_time < ANNOUNCER_TIMEOUT:
                time.sleep(0.5)
                announcement_response = load_json(DJ_RESPONSE_PATH)
                if announcement_response and announcement_response.get("request_timestamp") == announcement_request["timestamp"]:
                    log_event("response_received", mode="generate_announcement", duration=time.time() - start_time)
                    os.remove(DJ_RESPONSE_PATH)
                    announcer_file = announcement_response.get("announcer_path")
                    break
            
            if announcer_file and os.path.exists(announcer_file):
                 log_event("announcement_status", status="found", file=announcer_file)
            else:
                log_event("announcement_status", status="failed", error="missing_file")
                announcer_file = os.path.join(SCRIPT_DIR, "cache", "silent_announcer.mp3") 
                if not os.path.exists(announcer_file):
                    announcer_file = None
            
            
            # --- PHASE 4: Streaming (Pipe Output) ---
            
            segment_files = []
            if announcer_file and os.path.exists(announcer_file):
                segment_files.append(announcer_file)
            
            next_track_path = next_track_path if next_track_path else random.choice(all_tracks)
            segment_files.append(next_track_path) 
            
            with open(CONCAT_LIST_PATH, 'w', encoding='utf-8') as f:
                for file in segment_files:
                    safe_file = file.replace('\\', '/').replace("'", r"'\''")
                    f.write(f"file '{safe_file}'\n")

            # 2. FFmpeg command to output the raw MP3 data to stdout/pipe:1
            ffmpeg_command = [
                FFMPEG_BIN,
                "-f", "concat",
                "-safe", "0", 
                "-re", 
                "-i", CONCAT_LIST_PATH,
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                "-f", "mp3",
                "pipe:1" # Output to stdout/pipe
            ]

            log_event("stream_start", files=[os.path.basename(f) for f in segment_files])
            print(f"\n---> Streaming Segment: {', '.join(os.path.basename(f) for f in segment_files)}")
            
            subprocess.run(ffmpeg_command, check=True)
            log_event("stream_end", status="success", track_played=next_track_path)
            
            last_track_path = next_track_path
            
        except subprocess.CalledProcessError as e:
            error_output = e.stderr.decode('utf-8', errors='ignore') if e.stderr is not None else "No stderr captured."
            log_event("stream_end", status="crash", error=f"Code {e.returncode}", ffmpeg_output=error_output)
            print(f"FFmpeg Segment Error (Code {e.returncode}): Segment encoding failed or Icecast disconnected.")
            print(f"FFmpeg Error Output: {error_output}")
            time.sleep(1) 
            
        except Exception as e:
            log_event("critical_error", error=str(e))
            print(f"CRITICAL LOOP EXCEPTION: Script crashed during processing: {e}")
            time.sleep(5) 
            
if __name__ == "__main__":
    stream_radio()