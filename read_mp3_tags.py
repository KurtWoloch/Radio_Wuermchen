import json
from mutagen.mp3 import MP3
import glob

# File name is known to be in the workspace
file_path = '2 Unlimited - No limit.mp3'

try:
    audio = MP3(file_path)
    # Convert tags to simple strings for clean JSON output
    tags = {key: str(value) for key, value in audio.items()}
    print(json.dumps({"file": file_path, "tags": tags}, indent=2))
except Exception as e:
    # Print a clean error if the file is not a valid MP3 or tags can't be read
    print(json.dumps({"error": str(e), "path": file_path}))