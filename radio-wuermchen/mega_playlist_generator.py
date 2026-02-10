# Playlist Generator for Continuous Stream

import os
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYLIST_FILE = os.path.join(SCRIPT_DIR, "music.playlist")
ANNOUNCER_PATH = os.path.join(SCRIPT_DIR, "announcer.mp3") # Placeholder
MEGA_CONCAT_PATH = os.path.join(SCRIPT_DIR, "mega_concat.txt")

def create_mega_playlist():
    """Generates a single FFmpeg concat list containing all songs with announcements."""
    print("Generating infinite concat playlist (mega_concat.txt)...")
    
    try:
        with open(PLAYLIST_FILE, 'r', encoding='utf-8') as f:
            tracks = [line.strip() for line in f if line.strip()]
        
        if not tracks:
            print("Playlist is empty. Aborting.")
            return False

        if not os.path.exists(ANNOUNCER_PATH):
            print("CRITICAL: announcer.mp3 placeholder missing. Aborting.")
            return False

        with open(MEGA_CONCAT_PATH, 'w', encoding='utf-8') as f_out:
            for track_path in tracks:
                # Ensure paths are FFmpeg-compatible (forward slashes, escaped quotes)
                safe_announcer = ANNOUNCER_PATH.replace('\\', '/').replace("'", r"'\''")
                safe_track = track_path.replace('\\', '/').replace("'", r"'\''")
                
                # Write the announcement (silence) and the track
                f_out.write(f"file '{safe_announcer}'\n")
                f_out.write(f"file '{safe_track}'\n")
        
        print(f"Successfully generated {len(tracks) * 2} entries in mega_concat.txt.")
        return True

    except Exception as e:
        print(f"Error during mega playlist generation: {e}")
        return False

if __name__ == "__main__":
    create_mega_playlist()