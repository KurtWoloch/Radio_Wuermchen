import os
import glob
from mutagen.mp3 import MP3

# --- CONFIG ---
MUSIC_ROOT = r"E:\Daten\Radio Würmchen\Musik"
PLAYLIST_PATH = "music.playlist"

# --- TAG KEYS ---
ARTIST_TAG = 'TPE1'
TITLE_TAG = 'TIT2'
GENRE_TAG = 'TCON'

def generate_playlist(genre_filter=None):
    """
    Scans the music directory, filters by genre, and writes the list of paths
    to the music.playlist file for Liquidsoap.
    """
    print(f"Starting playlist generation. Filtering for genre: {genre_filter or 'ALL'}")
    
    # Use glob to find all MP3 files recursively
    search_path = os.path.join(MUSIC_ROOT, "**", "*.mp3")
    all_files = glob.glob(search_path, recursive=True)
    
    selected_paths = []
    
    for file_path in all_files:
        try:
            audio = MP3(file_path)
            
            # Extract Genre tag
            genres = audio.get(GENRE_TAG)
            
            is_match = True
            if genre_filter and genres:
                # Check if the desired genre is in the list of genres (Liquidsoap can read multiple)
                is_match = genre_filter.lower() in [str(g).lower() for g in genres]
            
            if is_match:
                selected_paths.append(file_path)
            
        except Exception as e:
            # Skip files that can't be read (e.g., corrupted, announcement.mp3)
            # print(f"Skipping {file_path}: {e}")
            pass

    # Write the selected paths to the Liquidsoap playlist file
    with open(PLAYLIST_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(selected_paths))
        
    print(f"Playlist generated successfully. {len(selected_paths)} songs selected and written to {PLAYLIST_PATH}.")
    return len(selected_paths)

if __name__ == "__main__":
    # --- EXAMPLE RUN ---
    # In a real scenario, the agent would update this call based on the current 'show'
    # We will test with a simple 'Dance' filter, or 'None' to list everything.
    generate_playlist(genre_filter="Dance")
    # For now, to ensure we get some output, I'll modify the script to list ALL files:
    # generate_playlist(genre_filter=None)
    
    # Wait, for the first run, let's list all files to ensure the path works.
    generate_playlist(genre_filter=None)