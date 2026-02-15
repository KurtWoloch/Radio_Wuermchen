# tts_manager.py

import subprocess
import time
import os
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
TTS_GENERATOR_SCRIPT = BASE_DIR / "tts_generate.py"
ANNOUNCEMENT_SLOTS = 10  # number of rotating announcement files
ANNOUNCEMENT_MIN_AGE = 1800  # seconds (30 min) before a slot can be reused
PYTHON_BIN = "C:\\Program Files\\Python311\\python.exe"

# --- HELPERS (Stubs/assumed imports) ---
def log(msg):
    print(f"[TTS_MANAGER] {msg}")

# --- CORE FUNCTIONS ---

def get_next_announcement_slot():
    """Find the next available announcement slot that's old enough to reuse."""
    now = time.time()
    
    # First pass: find a slot that either doesn't exist or is old enough
    for i in range(1, ANNOUNCEMENT_SLOTS + 1):
        mp3_path = BASE_DIR / f"temp_announcement{i}.mp3"
        if not os.path.exists(mp3_path):
            return i
        age = now - os.path.getmtime(mp3_path)
        if age >= ANNOUNCEMENT_MIN_AGE:
            return i
    
    # All slots are too young — pick the oldest one
    oldest_slot = 1
    oldest_age = 0
    for i in range(1, ANNOUNCEMENT_SLOTS + 1):
        mp3_path = BASE_DIR / f"temp_announcement{i}.mp3"
        age = now - os.path.getmtime(mp3_path)
        if age > oldest_age:
            oldest_age = age
            oldest_slot = i
    
    log(f"WARNING: All announcement slots are younger than {ANNOUNCEMENT_MIN_AGE}s. Reusing oldest (slot {oldest_slot}, {int(oldest_age)}s old).")
    return oldest_slot

def generate_announcement_audio(text_content):
    """Generates announcement audio using tts_generate.py with rotating file slots."""
    
    slot = get_next_announcement_slot()
    txt_file = BASE_DIR / f"temp_announcement{slot}.txt"
    mp3_file = BASE_DIR / f"temp_announcement{slot}.mp3"
    
    with open(str(txt_file), 'w', encoding='utf-8') as f:
        f.write(text_content)
        
    log(f"Generating announcement audio (slot {slot}): '{text_content[:30]}...'")

    command = [PYTHON_BIN, str(TTS_GENERATOR_SCRIPT), str(txt_file)]
    
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR)
        )
        
        log(f"TTS Generation successful (slot {slot}).")
        return mp3_file
        
    except subprocess.CalledProcessError as e:
        log(f"TTS Generation FAILED (Code {e.returncode}). Stderr: {e.stderr.strip()}")
        return None
    finally:
        # Clean up temporary text file
        if os.path.exists(txt_file):
            os.remove(str(txt_file))
