# Fallback Streamer (for continuous connection)

import subprocess
import os
import time

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_BIN = "C:/msys64/mingw64/bin/ffmpeg.exe"
SILENCE_FILE = os.path.join(SCRIPT_DIR, "announcer.mp3") # Using the 2s silent placeholder

def stream_fallback():
    """Starts a persistent, looping silence stream to act as an Icecast fallback."""
    print("Starting FALLBACK Streamer (Persistent Silence Loop)...")
    
    # FALLBACK_URL MUST BE A DIFFERENT MOUNTPOINT
    FALLBACK_URL = "icecast://source:BenandBen2026@localhost:8000/silent_stream.mp3"
    
    # -re loops the input stream infinitely for continuous connection
    ffmpeg_command = [
        FFMPEG_BIN,
        "-re", 
        "-stream_loop", "-1",  # Loop infinitely
        "-i", SILENCE_FILE,
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-f", "mp3",
        "-content_type", "audio/mpeg",
        FALLBACK_URL
    ]
    
    try:
        # Run FFmpeg and keep it running indefinitely
        subprocess.run(ffmpeg_command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"CRITICAL FALLBACK ERROR: FFmpeg failed: {e.stderr.strip()}")
    except FileNotFoundError:
        print(f"CRITICAL ERROR: FFmpeg not found at '{FFMPEG_BIN}'.")

if __name__ == "__main__":
    stream_fallback()