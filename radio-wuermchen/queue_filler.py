# Queue Filler
#
# Watches for the signal file (queue_low.signal) and appends the next
# track from the playlist to queue.txt when it appears.
#
# On startup, picks a random position in the playlist and pushes one
# track to the queue. Then watches for the signal file in a loop.

import os
import time
import random

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(SCRIPT_DIR, "queue.txt")
SIGNAL_FILE = os.path.join(SCRIPT_DIR, "queue_low.signal")
PLAYLIST_FILE = os.path.join(SCRIPT_DIR, "music.playlist")
LOG_FILE = os.path.join(SCRIPT_DIR, "queue_filler.log")
POLL_INTERVAL = 2  # seconds between checks for signal file

# --- LOGGING ---
def log(msg):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

# --- PLAYLIST ---
def load_playlist():
    """Load the full playlist from file. Returns list of paths."""
    try:
        with open(PLAYLIST_FILE, 'r', encoding='utf-8') as f:
            tracks = [line.strip() for line in f if line.strip()]
        return tracks
    except FileNotFoundError:
        log(f"ERROR: Playlist file not found: {PLAYLIST_FILE}")
        return []

# --- QUEUE OPERATIONS ---
def append_to_queue(track):
    """Append a single track path to the end of the queue file."""
    with open(QUEUE_FILE, 'a', encoding='utf-8') as f:
        f.write(track + '\n')
    log(f"Appended to queue: {os.path.basename(track)}")

def delete_signal():
    """Delete the signal file after processing it."""
    try:
        os.remove(SIGNAL_FILE)
        log("Signal file deleted.")
    except FileNotFoundError:
        pass
    except Exception as e:
        log(f"Error deleting signal file: {e}")

# --- MAIN ---
def main():
    log("=" * 60)
    log("Queue filler starting up.")

    playlist = load_playlist()
    if not playlist:
        log("ERROR: Playlist is empty. Exiting.")
        return

    log(f"Playlist loaded: {len(playlist)} tracks.")

    # Pick a random starting position
    position = random.randint(0, len(playlist) - 1)
    log(f"Starting at position {position}: {os.path.basename(playlist[position])}")

    # Push first track to queue
    append_to_queue(playlist[position])
    position = (position + 1) % len(playlist)

    # Watch loop
    log("Watching for signal file...")
    while True:
        if os.path.exists(SIGNAL_FILE):
            log(f"Signal detected. Adding track #{position}: {os.path.basename(playlist[position])}")
            append_to_queue(playlist[position])
            delete_signal()
            position = (position + 1) % len(playlist)
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
