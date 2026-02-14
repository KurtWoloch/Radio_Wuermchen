# Queue-Based Streamer (Black Box)
# 
# This script reads audio file paths from a queue file (one per line),
# streams them via FFmpeg to stdout (for piping to Icecast), and removes
# each entry after it finishes streaming.
#
# It does NOT handle DJ logic, TTS, or playlist selection.
# An external process is responsible for keeping the queue filled.
#
# Signal file: when the queue has only 1 item left, a signal file is
# written so the external queue-filler knows to add more tracks.
# When the queue is empty, the last played track is repeated.

import subprocess
import sys
import os
import time
# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(SCRIPT_DIR, "queue.txt")
SIGNAL_FILE = os.path.join(SCRIPT_DIR, "queue_low.signal")
FFMPEG_BIN = "C:/msys64/mingw64/bin/ffmpeg.exe"
CONCAT_LIST_PATH = os.path.join(SCRIPT_DIR, "temp_concat_streamer.txt")
LOG_FILE = os.path.join(SCRIPT_DIR, "streamer.log")

# --- LOGGING (to file, never to stderr which would corrupt the pipe) ---
def log(msg):
    """Write log messages to a file. Never use print() or stderr."""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

# --- QUEUE OPERATIONS ---
def read_queue():
    """Read all lines from the queue file. Returns list of file paths."""
    try:
        with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        return lines
    except FileNotFoundError:
        return []

def write_queue(lines):
    """Overwrite the queue file with the given lines."""
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line + '\n')

def pop_queue():
    """
    Read the queue, return the first item, and rewrite the queue without it.
    If only one item remains, don't remove it (repeat mode) and write signal.
    Returns (file_path, is_last) tuple, or (None, False) if empty.
    """
    lines = read_queue()
    if not lines:
        return None, False
    
    first = lines[0]
    
    if len(lines) == 1:
        # Last item: don't remove, write signal file
        write_signal()
        log(f"Queue has 1 item left (repeat mode): {first}")
        return first, True
    
    if len(lines) == 2:
        # About to become 1 after pop: write signal now
        write_signal()
        log(f"Queue down to 2 items, signaling low.")
    
    # Remove the first item
    write_queue(lines[1:])
    return first, False

def write_signal():
    """Write the signal file to notify the queue-filler."""
    try:
        with open(SIGNAL_FILE, 'w', encoding='utf-8') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as e:
        log(f"Error writing signal file: {e}")

# --- STREAMING ---
def stream_file(file_path):
    """
    Stream a single audio file to stdout using FFmpeg with -re (real-time).
    Returns True on success, False on error.
    """
    if not os.path.exists(file_path):
        log(f"ERROR: File not found: {file_path}")
        return False
    
    # Write concat list with single file (keeps format consistent,
    # easy to extend to announcement+song pairs later)
    safe_path = file_path.replace('\\', '/').replace("'", r"'\''")
    with open(CONCAT_LIST_PATH, 'w', encoding='utf-8') as f:
        f.write(f"file '{safe_path}'\n")
    
    ffmpeg_command = [
        FFMPEG_BIN,
        "-f", "concat",
        "-safe", "0",
        "-re",
        "-i", CONCAT_LIST_PATH,
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-f", "mp3",
        "pipe:1"
    ]
    
    try:
        # stdout goes to the pipe chain (outer FFmpeg -> Icecast)
        # stderr goes to /dev/null to avoid corrupting the pipe
        result = subprocess.run(
            ffmpeg_command,
            check=True,
            stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError as e:
        log(f"FFmpeg error (code {e.returncode}) for: {file_path}")
        return False

# --- MAIN LOOP ---
def main():
    log("=" * 60)
    log("Streamer starting up.")
    
    # Check initial queue
    initial = read_queue()
    if not initial:
        log("ERROR: Queue file is empty or missing. Nothing to stream.")
        log(f"Create {QUEUE_FILE} with at least one audio file path per line.")
        sys.exit(1)
    
    log(f"Queue loaded with {len(initial)} items. First: {initial[0]}")
    
    last_played = None
    
    while True:
        file_path, is_last = pop_queue()
        
        if file_path is None:
            # Queue completely empty (shouldn't happen due to repeat logic, but safety net)
            if last_played:
                log(f"Queue empty, repeating last played: {last_played}")
                file_path = last_played
                write_signal()
            else:
                log("Queue empty and nothing was ever played. Waiting 5s...")
                time.sleep(5)
                continue
        
        log(f"Streaming: {os.path.basename(file_path)}")
        success = stream_file(file_path)
        
        if success:
            last_played = file_path
            log(f"Finished: {os.path.basename(file_path)}")
        else:
            log(f"Failed to stream: {file_path}, skipping.")
            # Small delay to avoid tight error loops
            time.sleep(1)

if __name__ == "__main__":
    main()
