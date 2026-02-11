# Dynamic Segment Streamer (Pipe-Writer Mode with Local SAPI TTS)

import subprocess
import time
import os
import random
from itertools import cycle
import re
import json

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PLAYLIST_FILE = os.path.join(SCRIPT_DIR, "music.playlist")
FFMPEG_BIN = "C:/msys64/mingw64/bin/ffmpeg.exe"
CONCAT_LIST_PATH = os.path.join(SCRIPT_DIR, "temp_concat.txt") 

# Path for the temporary text and audio files
ANNOUNCEMENT_TEXT_PATH = os.path.join(SCRIPT_DIR, "temp_announcement.txt")
ANNOUNCEMENT_WAV_PATH = os.path.join(SCRIPT_DIR, "temp_announcement.wav")

# --- UTILITIES ---

def get_playlist(file_path):
    """Reads the playlist file and returns a shuffled list of file paths."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tracks = [line.strip() for line in f if line.strip()]
        random.shuffle(tracks)
        return tracks
    except FileNotFoundError:
        print(f"Error: Playlist file not found at {file_path}")
        return []

def get_artist_title(track_path):
    """Simple parser to extract Artist - Title from a filename."""
    base_name = os.path.basename(track_path)
    name_no_ext = os.path.splitext(base_name)[0].strip()
    match = re.match(r'^(.*?)\s*-\s*(.*)$', name_no_ext) 
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "Unknown Artist", name_no_ext

def generate_announcement_text(artist, title):
    """Generates a simple announcement text."""
    # This can be expanded later to include more VB5-like logic.
    return f"Hello, this is Radio Worm. Up next is {artist} with their song, {title}. Stay tuned."


def get_announcer_file(artist, title):
    """
    Generates and caches the announcement file using local SAPI via PowerShell.
    """
    announcement_text = generate_announcement_text(artist, title)
    
    # 1. Define the required unique announcement MP3 file path in the cache
    announcer_filename = re.sub(r'[^a-zA-Z0-9]', '_', announcement_text)[:40] + ".mp3"
    dynamic_announcer_path = os.path.join(SCRIPT_DIR, "cache", announcer_filename)

    # 2. Check if the final MP3 file already exists (cache hit)
    if os.path.exists(dynamic_announcer_path):
        print(f"Using cached announcement: {announcer_filename}")
        return dynamic_announcer_path
    
    print(f"\
---> Generating new announcement for: {artist} - {title}")
    os.makedirs(os.path.join(SCRIPT_DIR, "cache"), exist_ok=True)
    
    # --- Step A: Write text to temporary file ---
    with open(ANNOUNCEMENT_TEXT_PATH, 'w', encoding='utf-8') as f:
        f.write(announcement_text)
    
    # --- Step B: Convert text to WAV using PowerShell SAPI ---
    # We use a temp WAV file for SAPI output
    powershell_cmd = f"$speak = New-Object -ComObject 'SAPI.SpVoice'; $stream = New-Object -ComObject 'SAPI.SpFileStream'; "
    powershell_cmd += f"$stream.Open('{ANNOUNCEMENT_WAV_PATH}', 3, $false); $speak.AudioOutputStream = $stream; "
    powershell_cmd += f"$voice = $speak.GetVoices() | Where-Object {{ $_.GetAttribute('Language') -eq '409' -and $_.GetDescription() -eq 'Microsoft Zira Desktop - English (United States)' }}; "
    powershell_cmd += f"$speak.Voice = $voice; $speak.Speak([System.IO.File]::ReadAllText('{ANNOUNCEMENT_TEXT_PATH}')); $stream.Close(); $speak = $null;"
    
    sapi_command = ["powershell", "-Command", powershell_cmd]
    
    try:
        subprocess.run(sapi_command, check=True, capture_output=True, text=True)
        print("SAPI conversion successful.")
    except subprocess.CalledProcessError as e:
        print(f"SAPI Error: {e.stderr}")
        return None
    
    # --- Step C: Convert temporary WAV to final MP3 using FFmpeg ---
    ffmpeg_encode_command = [
        FFMPEG_BIN,
        "-i", ANNOUNCEMENT_WAV_PATH,
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        dynamic_announcer_path
    ]
    
    try:
        subprocess.run(ffmpeg_encode_command, check=True, capture_output=True)
        print(f"MP3 encoding successful, saved to cache: {announcer_filename}")
        # Cleanup temporary WAV file
        os.remove(ANNOUNCEMENT_WAV_PATH)
        return dynamic_announcer_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg Encoding Error: {e.stderr.decode('utf-8')}")
        return None
    
# --- MAIN STREAMING LOGIC ---

def stream_radio():
    # ... (rest of stream_radio remains the same, except for the new announcement function)
    print("Starting Pipe-Writer (FFmpeg Segment Generator)...")
    
    os.makedirs(os.path.join(SCRIPT_DIR, "cache"), exist_ok=True)

    tracks = get_playlist(PLAYLIST_FILE)
    if not tracks:
        print("Playlist is empty. Exiting.")
        return

    track_cycle = cycle(tracks)
    
    for track_path in track_cycle:
        try:
            artist, title = get_artist_title(track_path)
            # The announcement logic is now dynamic (SAPI-based)
            announcer_file = get_announcer_file(artist, title) 
            
            # 1. Create FFmpeg Concat List
            segment_files = []
            if announcer_file:
                segment_files.append(announcer_file)
            segment_files.append(track_path)

            with open(CONCAT_LIST_PATH, 'w', encoding='utf-8') as f:
                for file in segment_files:
                    safe_file = file.replace('\\', '/').replace("'", r"'\''")
                    f.write(f"file '{safe_file}'\n")

            # 2. FFmpeg command to output the raw MP3 data to stdout
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

            print(f"\
---> Streaming Segment: {', '.join(os.path.basename(f) for f in segment_files)}")
            
            subprocess.run(ffmpeg_command, check=True)
            
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg Segment Error (Code {e.returncode}): Segment encoding failed.")
            continue
        except Exception as e:
            print(f"CRITICAL LOOP EXCEPTION: Script crashed during processing: {e}")
            continue 

if __name__ == "__main__":
    stream_radio()