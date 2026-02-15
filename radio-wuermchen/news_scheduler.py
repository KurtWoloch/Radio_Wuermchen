# news_scheduler.py

import subprocess
import time
import json
from pathlib import Path
import os
import re

# --- CONFIGURATION ---
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
NEWS_MANAGER_SCRIPT = BASE_DIR / "news_manager.py"
NEWS_HEADLINES_INTERVAL = 3600  # seconds (60 min) - how often to do a full headlines segment
NEWS_STATE_FILE = BASE_DIR / "news_state.json"
PYTHON_BIN = "C:\\Program Files\\Python311\\python.exe"

# --- HELPERS (Stubs for functions needed from orchestrator) ---
def load_json(path):
    try:
        with open(str(path), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(path, data):
    with open(str(path), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def log(msg):
    print(f"[NEWS_SCHEDULER] {msg}")

# --- NEWS MANAGER WRAPPERS ---

def news_update():
    """Run news_manager.py update. Returns True on success."""
    try:
        result = subprocess.run(
            [PYTHON_BIN, str(NEWS_MANAGER_SCRIPT), "update"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=60
        )
        log(f"Update result: {result.returncode == 0}")
        if result.returncode != 0:
            log(f"News update error: {result.stderr.strip()}")
            return False
        return True
    except Exception as e:
        log(f"News update exception: {e}")
        return False

def news_get_headlines():
    """Run news_manager.py headlines. Returns parsed JSON or None."""
    try:
        result = subprocess.run(
            [PYTHON_BIN, str(NEWS_MANAGER_SCRIPT), "headlines"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=15
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        log(f"News headlines error: {e}")
    return None

def news_get_next_story():
    """Run news_manager.py next_story. Returns parsed JSON or None."""
    try:
        result = subprocess.run(
            [PYTHON_BIN, str(NEWS_MANAGER_SCRIPT), "next_story"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get('id') and data.get('story'):
                return data
    except Exception as e:
        log(f"News next_story error: {e}")
    return None

def news_mark_presented(story_id):
    """Run news_manager.py mark <id>."""
    try:
        subprocess.run(
            [PYTHON_BIN, str(NEWS_MANAGER_SCRIPT), "mark", story_id],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=10
        )
        log(f"Marked story {story_id} as presented.")
    except Exception as e:
        log(f"News mark error: {e}")

# --- STATE MANAGEMENT ---

def load_news_state():
    """Load persistent news state (last headlines time, etc.)."""
    return load_json(NEWS_STATE_FILE) or {'last_headlines_at': 0}

def save_news_state(state):
    save_json(NEWS_STATE_FILE, state)

# --- SCHEDULING LOGIC ---

def get_news_instruction():
    """
    Determine the news instruction for this DJ cycle.
    Returns (instruction_text, story_id_to_mark_after_success) or (None, None).
    Story ID is returned as a string if it's a deep-dive requiring marking.
    """
    # Always try to update (respects its own 60-min cache internally)
    news_update()

    news_state = load_news_state()
    now = time.time()
    time_since_headlines = now - news_state.get('last_headlines_at', 0)

    # 1. Check for Headline Segment (Every NEWS_HEADLINES_INTERVAL)
    if time_since_headlines >= NEWS_HEADLINES_INTERVAL:
        headlines_data = news_get_headlines()
        if headlines_data and headlines_data.get('headlines'):
            headline_list = headlines_data['headlines']

            # Build headline text for the DJ
            parts = []
            if headlines_data.get('breaking'):
                parts.append(f"BREAKING NEWS: {headlines_data['breaking']}")

            # Group by type for clarity
            top = [h['headline'] for h in headline_list if h['type'] == 'top']
            regular = [h['headline'] for h in headline_list if h['type'] == 'regular']
            quick = [h['headline'] for h in headline_list if h['type'] == 'quicklink']

            if top:
                parts.append("Top stories: " + "; ".join(top))
            if regular:
                parts.append("Also in the news: " + "; ".join(regular[:5]))
            if quick:
                parts.append("In brief: " + "; ".join(quick[:5]))

            headline_text = "\n".join(parts)

            instruction = (
                f"NEWS SEGMENT: It's time for the hourly news update! Here are the current headlines:\n\n"
                f"{headline_text}\n\n"
                "Please present these headlines to the listeners as a news bulletin in your own words. "
                "Cover the top stories first, then briefly mention a few of the other headlines. "
                "After the news, suggest and introduce a song that fits the overall mood of today's news."
            )

            # Update state — mark headlines as delivered and reset deep dive tracking
            news_state['last_headlines_at'] = now
            news_state['last_deep_dive_id'] = None
            save_news_state(news_state)

            log(f"News: HEADLINES segment ({len(headline_list)} headlines)")
            return instruction, None

    # 2. Check for Deep Dive Story
    deep_dive_id = news_state.get('last_deep_dive_id')
    
    # If last deep dive was successful (i.e., ID exists and is not PENDING), look for a new one
    if deep_dive_id and deep_dive_id != "PENDING":
        log(f"Deep dive ID {deep_dive_id} was presented. Resetting for next cycle to find new story.")
        news_state['last_deep_dive_id'] = None
        save_news_state(news_state)
        deep_dive_id = None # Reset to search below

    if not deep_dive_id or deep_dive_id == "PENDING":
        # Look for the next unpresented story with content
        story = news_get_next_story()
        
        if story:
            story_id = story.get('id')
            if not story_id:
                log("Warning: Found story with no ID, skipping deep dive logic.")
                return None, None

            # Mark as pending immediately to prevent another loop finding it before this one succeeds
            news_state['last_deep_dive_id'] = "PENDING"
            save_news_state(news_state)
            
            instruction = (
                f"NEWS DEEP DIVE: Please present the following news story to the listeners in your own words.\n\n"
                f"Headline: {story['headline']}\n"
                f"Story: {story['story']}\n\n"
                "Summarize this story engagingly for the radio audience, then suggest and introduce "
                "a song that fits the topic or mood of this story."
            )
            log(f"News: DEEP DIVE on '{story['headline'][:50]}...' (id: {story_id})")
            return instruction, story_id # Return ID string here for marking later
        else:
            log("No more new stories with content to present.")
            # Ensure state is clean if we stop finding new stories
            if news_state.get('last_deep_dive_id') == 'PENDING':
                news_state['last_deep_dive_id'] = None
                save_news_state(news_state)
            return None, None

    # No news to present
    log("News: subtle mode (cached/no new content).")
    return None, None