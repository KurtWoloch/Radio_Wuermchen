# DJ Orchestrator (Glue Script)
#
# Monitors the queue_low.signal file, triggers the standalone DJ,
# handles TTS generation for the announcement, and feeds the results
# back into the main queue.

import subprocess
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime
import re

# --- IMPORTS FROM NEW MANAGERS ---
from weather_manager import get_weather_forecast, WEATHER_RESULT
from tts_manager import generate_announcement_audio
from news_scheduler import get_news_instruction, news_mark_presented
import charts_scraper

# --- CONFIGURATION ---
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = BASE_DIR / "queue.txt"
SIGNAL_FILE = BASE_DIR / "queue_low.signal"
REQUEST_FILE = BASE_DIR / "dj_request.json"
RESPONSE_FILE = BASE_DIR / "dj_response.json"
PLAYLIST_FILE = BASE_DIR / "music.playlist"
DJ_BRAIN_SCRIPT = BASE_DIR / "dj_brain.py"
LOG_FILE = BASE_DIR / "orchestrator.log"
WISHLIST_FILE = BASE_DIR / "Wishlist.txt"
LISTENER_REQUEST_FILE = BASE_DIR / "listener_request.txt"
SUGGESTION_POOL_FILE = BASE_DIR / "suggestion_pool.txt"
HISTORY_FILE = BASE_DIR / "dj_history.json" # NEW: Added History file constant
SHOWS_SCHEDULE_FILE = BASE_DIR / "shows_schedule.json"
CHARTS_LIBRARY_FILE = BASE_DIR / "charts_in_library.json"
TRACK_ALIASES_FILE = BASE_DIR / "track_aliases.json"

PYTHON_BIN = "C:\\Program Files\\Python311\\python.exe"
POLL_INTERVAL = 3  # seconds between checks
ICECAST_STATUS_URL = "http://localhost:8000/status-json.xsl"
MAX_ARTIST_SUGGESTIONS = 50 # Maximum tracks to offer the DJ if suggestion fails
MAX_POOL_SUGGESTIONS = 50   # Maximum tracks to offer from the suggestion pool
MAX_DJ_ATTEMPTS = 5 # Maximum times to re-prompt the DJ per signal event

# --- HELPERS ---
def get_listener_count():
    """Query Icecast for the current number of listeners.
    Returns the raw count (includes proxy connections from listener_server)."""
    try:
        import urllib.request
        with urllib.request.urlopen(ICECAST_STATUS_URL, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        source = data.get("icestats", {}).get("source", {})
        # source can be a list (multiple mountpoints) or a dict (single)
        if isinstance(source, list):
            return sum(s.get("listeners", 0) for s in source)
        return source.get("listeners", 0)
    except Exception:
        return -1  # unknown / error

def has_listeners():
    """Check if there are real listeners (beyond the listener_server proxy).
    The web listener server keeps one persistent connection per web listener,
    but even with 0 web listeners there may be 0 proxy connections.
    We consider >0 as having listeners."""
    count = get_listener_count()
    if count < 0:
        return True  # assume yes if we can't check
    log(f"Icecast listener count: {count}")
    return count > 0

def log(msg):
    """Write log messages to a file."""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def load_json(path):
    """Load JSON data, handling missing files gracefully."""
    path_str = str(path)
    try:
        with open(path_str, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        if path_str.endswith("history.json"):
            return []
        return {}
    except json.JSONDecodeError as e:
        log(f"Error reading JSON file {path_str}: {e}")
        return {}

def save_json(path, data):
    with open(str(path), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def read_last_line(path):
    """Reads the last non-empty line from a file."""
    try:
        with open(str(path), 'rb') as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            if file_size == 0:
                return None
            
            chunk_size = 1024
            buffer = b''
            while f.tell() > 0:
                read_size = min(chunk_size, f.tell())
                f.seek(-read_size, os.SEEK_CUR)
                chunk = f.read(read_size)
                buffer = chunk + buffer
                
                if b'\n' in chunk:
                    return buffer.split(b'\n')[-2].decode('utf-8').strip()
                
                if f.tell() == 0:
                    return buffer.decode('utf-8').strip()

            return buffer.decode('utf-8').strip()
    except Exception as e:
        log(f"Error reading last line from {path}: {e}")
        return None

def delete_signal():
    """Delete the signal file and its lock."""
    for f in [str(SIGNAL_FILE), str(SIGNAL_FILE) + ".lock"]:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    log("Signal file deleted.")

def read_and_clear_listener_request():
    """Read listener request from file and delete the file."""
    try:
        with open(str(LISTENER_REQUEST_FILE), 'r', encoding='utf-8') as f:
            request = f.read().strip()
        os.remove(str(LISTENER_REQUEST_FILE))
        log("Listener request read and file deleted.")
        return request if request else None
    except FileNotFoundError:
        return None
    except Exception as e:
        log(f"Error reading/clearing listener request file: {e}")
        return None

# --- QUEUE MANAGEMENT ---
def append_to_queue(track_path):
    """Append a track path to the queue file."""
    with open(str(QUEUE_FILE), 'a', encoding='utf-8') as f:
        f.write(track_path + '\n')
    log(f"Appended to queue: {os.path.basename(track_path)}")

def append_to_wishlist(track_suggestion):
    """Append a track suggestion to the Wishlist file."""
    with open(str(WISHLIST_FILE), 'a', encoding='utf-8') as f:
        f.write(track_suggestion + '\n')
    log(f"Appended to wishlist: {track_suggestion}")

# --- SUGGESTION POOL ---
def read_suggestion_pool(pool_file=None):
    """Read the suggestion pool file. Returns list of 'Artist - Track' strings."""
    target = pool_file or str(SUGGESTION_POOL_FILE)
    try:
        with open(target, 'r', encoding='latin-1') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        return lines
    except FileNotFoundError:
        return []

def remove_from_suggestion_pool(track_name):
    """Remove a track from the suggestion pool (by matching Artist - Track name in filename)."""
    pool = read_suggestion_pool()
    if not pool:
        return
    
    track_lower = track_name.lower()
    new_pool = []
    removed = False
    for line in pool:
        if not removed and line.lower() in track_lower:
            log(f"Removed from suggestion pool: {line}")
            removed = True
        else:
            new_pool.append(line)
    
    if removed:
        with open(str(SUGGESTION_POOL_FILE), 'w', encoding='latin-1') as f:
            for line in new_pool:
                f.write(line + '\n')

def get_pool_suggestions(max_count=MAX_POOL_SUGGESTIONS, pool_file=None):
    """Get the top N suggestions from the pool."""
    pool = read_suggestion_pool(pool_file=pool_file)
    return pool[:max_count]

def remove_from_pool_file(pool_file_path, track_name):
    """Remove a track from a specific pool file by matching against the track filename."""
    try:
        with open(pool_file_path, 'r', encoding='latin-1') as f:
            lines = [line.rstrip('\n').rstrip('\r') for line in f]
    except FileNotFoundError:
        return

    track_lower = track_name.lower()
    new_lines = []
    removed = False
    for line in lines:
        stripped = line.strip()
        if not removed and stripped and not stripped.startswith('#'):
            # Strip chart annotations for comparison
            clean_line = re.sub(r'\s*\(.*?\)\s*$', '', stripped).strip()
            if clean_line.lower() in track_lower:
                log(f"Removed from pool {os.path.basename(pool_file_path)}: {stripped}")
                removed = True
                continue
        new_lines.append(line)

    if removed:
        with open(pool_file_path, 'w', encoding='latin-1') as f:
            for line in new_lines:
                f.write(line + '\n')

def remove_exact_from_pool_file(pool_file_path, exact_entry):
    """Remove a specific entry from a pool file by exact text match."""
    try:
        with open(pool_file_path, 'r', encoding='latin-1') as f:
            lines = [line.rstrip('\n').rstrip('\r') for line in f]
    except FileNotFoundError:
        return

    new_lines = []
    removed = False
    for line in lines:
        if not removed and line.strip() == exact_entry.strip():
            log(f"Removed from pool {os.path.basename(pool_file_path)}: {line.strip()}")
            removed = True
            continue
        new_lines.append(line)

    if removed:
        with open(pool_file_path, 'w', encoding='latin-1') as f:
            for line in new_lines:
                f.write(line + '\n')

def fallback_queue_from_pool(show_overrides, playlist):
    """When the DJ is unavailable, pick the next song from the suggestion pool,
    match it against the library, queue it, and remove it from the pool.
    Returns the queued track path or None."""
    show_pool_file = str(BASE_DIR / show_overrides["suggestion_pool"]) if show_overrides.get("suggestion_pool") else None
    actual_pool_file = show_pool_file or str(SUGGESTION_POOL_FILE)
    pool = read_suggestion_pool(pool_file=show_pool_file)
    
    for suggestion in pool:
        # Strip chart annotations like "(currently at #xx in the Austrian charts)"
        clean_name = re.sub(r'\s*\(.*?\)\s*$', '', suggestion).strip()
        cleaned = clean_suggestion_for_matching(clean_name)
        
        for p_track in playlist:
            p_filename = os.path.basename(p_track)
            if cleaned.lower() in p_filename.lower():
                log(f"FALLBACK (no DJ): Queueing from pool: {p_filename}")
                append_to_queue(p_track)
                # Remove the exact pool entry we matched, not a fuzzy re-match
                remove_exact_from_pool_file(actual_pool_file, suggestion)
                return p_track
    
    log("FALLBACK: No matching tracks found in suggestion pool.")
    return None

# --- ARTIST MATCHING ---
def parse_artist_from_suggestion(suggestion):
    """Extracts the artist part from an 'Artist - Title' string."""
    if " - " in suggestion:
        return suggestion.split(" - ", 1)[0].strip()
    return None

def clean_suggestion_for_matching(suggestion):
    """Strips versioning/subtitles and featured-artist tags from the suggested track name for better matching."""
    cleaned = re.sub(r'\s*\(.*?\)\s*', ' ', suggestion).strip()
    # Strip "ft./feat. <name>" only up to the " - " separator (preserve the title)
    cleaned = re.sub(r'\s*(?:ft\.|feat\.)\s*[^-]+', '', cleaned, count=1, flags=re.IGNORECASE).strip()
    # Clean up any leftover leading/trailing hyphens or whitespace
    cleaned = re.sub(r'^[\s-]+|[\s-]+$', '', cleaned).strip()
    return cleaned

def find_news_relevant_tracks(news_text, playlist, max_results=10):
    """Extract quoted strings from news text and find matching tracks in the playlist.
    Handles English quotes ("..."), German lower-upper quotes (\u201e...\u201c), and
    guillemets (\u00bb...\u00ab / \u00ab...\u00bb). Returns list of (track_path, quote_matched) tuples."""
    if not news_text:
        return []
    
    # Extract quoted strings (min 2 chars) — English, German, and guillemet styles
    quotes = re.findall(r'[""\u201e\u201c\u00ab\u00bb](.{2,}?)[""\u201c\u201e\u00ab\u00bb]', news_text)
    if not quotes:
        return []
    
    log(f"News quotes extracted: {quotes[:15]}")
    
    # Find playlist matches for each quoted string
    matches = []
    seen_tracks = set()
    for quote in quotes:
        quote_lower = quote.lower().strip()
        if len(quote_lower) < 3:  # skip very short quotes
            continue
        for p_track in playlist:
            if p_track in seen_tracks:
                continue
            p_filename = os.path.basename(p_track).lower()
            if quote_lower in p_filename:
                matches.append((p_track, quote))
                seen_tracks.add(p_track)
    
    if not matches:
        return []
    
    log(f"News quote matches: {len(matches)} tracks found")
    
    # If too many matches, filter by artist appearing in the news text
    if len(matches) > max_results:
        news_lower = news_text.lower()
        filtered = []
        for p_track, quote in matches:
            artist = parse_artist_from_suggestion(os.path.splitext(os.path.basename(p_track))[0])
            if artist and artist.lower() in news_lower:
                filtered.append((p_track, quote))
        if filtered:
            log(f"News matches filtered by artist presence: {len(filtered)} tracks")
            matches = filtered[:max_results]
        else:
            # No artist matches — just take the first batch
            matches = matches[:max_results]
    
    return matches

def apply_track_aliases(suggestion):
    """Check if the suggestion contains any known aliases and return
    a list of alternative spellings to try. Returns empty list if no alias matches."""
    aliases = load_json(str(TRACK_ALIASES_FILE))
    if not aliases or "aliases" not in aliases:
        return []
    
    suggestion_lower = suggestion.lower()
    alternatives = []
    for alias, proper in aliases["aliases"].items():
        if alias.lower() in suggestion_lower:
            # Replace the alias portion with the proper spelling
            replaced = re.sub(re.escape(alias), proper, suggestion, count=1, flags=re.IGNORECASE)
            alternatives.append(replaced)
            log(f"Alias match: '{alias}' -> '{proper}' (rewritten: '{replaced}')")
    return alternatives

def find_artist_alternatives(artist_name, playlist, max_results=MAX_ARTIST_SUGGESTIONS):
    """Finds up to max_results tracks from the playlist matching the artist name."""
    alternatives = []
    for p_track in playlist:
        filename = os.path.basename(p_track)
        if artist_name.lower() in filename.lower():
            alternatives.append(p_track)
            if len(alternatives) >= max_results:
                break
    return alternatives

# --- DJ COMMUNICATION ---
def trigger_dj(last_track, listener_input=None, instructions=None):
    """Writes request file, runs DJ brain, reads response."""
    
    request_data = {
        "last_track": last_track,
        "listener_input": listener_input,
        "instructions": instructions
    }
    with open(str(REQUEST_FILE), 'w', encoding='utf-8') as f:
        json.dump(request_data, f, indent=2)
    log(f"Wrote DJ request. Last Track: {last_track}. Listener Input: {listener_input}. Instructions: {instructions}")

    command = [PYTHON_BIN, str(DJ_BRAIN_SCRIPT)]
    log(f"Executing DJ Brain: {' '.join(command)}")
    
    try:
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, cwd=str(BASE_DIR)
        )
        log(f"DJ Brain finished. STDOUT: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        log(f"DJ Brain FAILED (Code {e.returncode}). Stderr: {e.stderr.strip()}")
        return None

    response = load_json(RESPONSE_FILE)
    
    # Delete response file immediately to prevent stale re-use
    try:
        os.remove(str(RESPONSE_FILE))
    except OSError:
        pass
    
    if not response or "error" in response:
        log(f"Failed to get valid response from DJ: {response}")
        return None
        
    return response


# --- SHOW SCHEDULE ---

SHOW_LOOKAHEAD_MINUTES = 4  # Start preparing a show this many minutes early

def get_active_show():
    """Check if a scheduled show is currently active or about to start
    (within SHOW_LOOKAHEAD_MINUTES). Returns show dict or None."""
    schedule = load_json(str(SHOWS_SCHEDULE_FILE))
    if not schedule or "shows" not in schedule:
        return None
    
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    # Look ahead: if a show starts in <=4 min, treat it as active already
    lookahead_minutes = (current_minutes + SHOW_LOOKAHEAD_MINUTES) % (24 * 60)
    
    for show in schedule["shows"]:
        sched = show.get("schedule", {})
        start_str = sched.get("start", "")
        end_str = sched.get("end", "")
        if not start_str or not end_str:
            continue
        
        try:
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
        except ValueError:
            continue
        
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        
        if end_min <= start_min:
            # Crosses midnight (e.g. 23:00 - 00:00)
            if current_minutes >= start_min or current_minutes < end_min:
                return show
            # Lookahead: about to start
            if lookahead_minutes >= start_min and current_minutes < start_min:
                return show
        else:
            if start_min <= current_minutes < end_min:
                return show
            # Lookahead: about to start
            if current_minutes < start_min and lookahead_minutes >= start_min:
                return show
    
    return None

def get_show_overrides(show):
    """Extract overrides from a show config, with defaults."""
    schedule = load_json(str(SHOWS_SCHEDULE_FILE))
    defaults = schedule.get("defaults", {}) if schedule else {}
    overrides = show.get("overrides", {}) if show else {}
    
    return {
        "music_style": overrides.get("music_style", defaults.get("music_style")),
        "dj_personality": overrides.get("dj_personality", defaults.get("dj_personality")),
        "suggestion_pool": overrides.get("suggestion_pool", defaults.get("suggestion_pool", "suggestion_pool.txt")),
        "news_enabled": overrides.get("news_enabled", defaults.get("news_enabled", True)),
        "signation": overrides.get("signation"),
    }

# --- MAIN LOOP ---
def main():
    log("=" * 60)
    log("DJ Orchestrator starting up.")
    
    last_track_played = None
    last_show_id = None  # Track show transitions
    last_charts_check = 0
    CHARTS_CHECK_INTERVAL = 86400  # 24 hours in seconds
    
    while True:
        
        listener_input = None
        
        # --- CHARTS CHECK (once per day) ---
        now_ts = time.time()
        if now_ts - last_charts_check > CHARTS_CHECK_INTERVAL:
            try:
                cache_file = str(BASE_DIR / "charts_cache.json")
                cache_age = None
                if os.path.exists(cache_file):
                    cache_age = now_ts - os.path.getmtime(cache_file)
                
                if cache_age is None or cache_age > CHARTS_CHECK_INTERVAL:
                    log("Charts cache is stale or missing. Running charts scraper...")
                    charts_scraper.main()
                    log("Charts scraper finished.")
                else:
                    log(f"Charts cache is fresh ({cache_age:.0f}s old). Skipping scrape.")
            except Exception as e:
                log(f"Charts scraper error (non-fatal): {e}")
            last_charts_check = now_ts
        
        if os.path.exists(SIGNAL_FILE):
            # Atomically claim the signal file to prevent duplicate processing
            lock_file = str(SIGNAL_FILE) + ".lock"
            try:
                os.rename(str(SIGNAL_FILE), lock_file)
            except (OSError, FileNotFoundError):
                # Another instance already claimed it
                log("Signal file disappeared (claimed by another instance). Skipping.")
                time.sleep(POLL_INTERVAL)
                continue
            log("Signal detected. Starting DJ cycle.")
            
            # Delete signal immediately to prevent duplicate cycles
            delete_signal()

            listener_input = read_and_clear_listener_request()

            # --- POWER SAVING MODE ---
            # If no listeners are connected, skip LLM/TTS and just queue
            # the next track from the suggestion pool. Listener requests
            # still get full treatment (someone is clearly listening).
            if not listener_input and not has_listeners():
                log("POWER SAVE: No listeners detected — skipping LLM/TTS, queueing from pool.")
                active_show = get_active_show()
                show_overrides = get_show_overrides(active_show)
                # Track show transitions even in power-save mode
                last_show_id = active_show.get("id") if active_show else None
                try:
                    with open(str(PLAYLIST_FILE), 'r', encoding='utf-8') as f:
                        playlist = [line.strip() for line in f if line.strip()]
                except FileNotFoundError:
                    playlist = []
                if playlist:
                    # Remember pool state before fallback picks a track
                    show_pool_file = str(BASE_DIR / show_overrides["suggestion_pool"]) if show_overrides.get("suggestion_pool") else None
                    actual_pool_file = show_pool_file or str(SUGGESTION_POOL_FILE)
                    pool_before = read_suggestion_pool(pool_file=show_pool_file)
                    
                    fallback_track = fallback_queue_from_pool(show_overrides, playlist)
                    if fallback_track:
                        last_track_played = fallback_track
                        # Re-append the used suggestion to rotate the pool
                        pool_after = read_suggestion_pool(pool_file=show_pool_file)
                        removed = [s for s in pool_before if s not in pool_after]
                        for entry in removed:
                            try:
                                # Read file to check if it ends with newline
                                with open(actual_pool_file, 'rb') as f:
                                    f.seek(0, 2)  # end of file
                                    if f.tell() > 0:
                                        f.seek(-1, 2)
                                        needs_newline = f.read(1) != b'\n'
                                    else:
                                        needs_newline = False
                                with open(actual_pool_file, 'a', encoding='latin-1') as f:
                                    if needs_newline:
                                        f.write('\n')
                                    f.write(entry + '\n')
                                log(f"POWER SAVE: Re-appended '{entry}' to pool (rotation mode).")
                            except Exception as e:
                                log(f"POWER SAVE: Failed to re-append to pool: {e}")
                time.sleep(POLL_INTERVAL)
                continue

            # --- PHASE 0: SHOW DETECTION & TRANSITION ---
            active_show = get_active_show()
            show_overrides = get_show_overrides(active_show)
            current_show_id = active_show.get("id") if active_show else None
            is_show_transition = (current_show_id != last_show_id)
            show_signation_track = None
            
            if active_show:
                log(f"Active show: {active_show['name']}")
            if is_show_transition:
                if active_show:
                    log(f"SHOW TRANSITION: '{last_show_id}' -> '{current_show_id}' ({active_show['name']})")
                else:
                    log(f"SHOW TRANSITION: '{last_show_id}' -> no show (freeform)")
                last_show_id = current_show_id
            
            # --- PHASE 1: CONTEXT GATHERING ---
            
            # Skip weather and news when:
            # - A listener request came in (focus on fulfilling it)
            # - A new show is starting (focus on the show intro)
            weather_instruction = None
            news_instruction = None
            news_context_payload = None
            skip_weather_news = False

            if listener_input:
                log(f"Listener request active — skipping weather/news to prioritize request: {listener_input}")
                skip_weather_news = True
            if is_show_transition and active_show:
                log(f"Show transition — skipping weather/news for show intro.")
                skip_weather_news = True
            if not skip_weather_news:
                # A. Weather Context
                weather_forecast = get_weather_forecast()
                weather_is_fresh = False
                if weather_forecast:
                    try:
                        age = time.time() - os.path.getmtime(WEATHER_RESULT)
                        weather_is_fresh = (age < 10)
                    except Exception:
                        pass

                    if weather_is_fresh:
                        weather_instruction = (
                            f"Current weather forecast for Vienna:\n{weather_forecast}\n\n"
                            "It's time for a weather update! Please present the full weather forecast to the listeners in your own words, "
                            "then suggest and introduce a song that fits the current weather mood."
                        )
                        log("Weather segment: FULL forecast mode (fresh scrape)")
                    else:
                        weather_instruction = (
                            f"Current weather for Vienna: {weather_forecast}\n"
                            "You may weave weather info naturally into your announcement if it fits, but don't repeat the full forecast."
                        )
                        log("Weather segment: subtle mode (cached)")

                # B. News Segment Check
                if show_overrides["news_enabled"]:
                    news_instruction, news_context_payload = get_news_instruction()
                else:
                    news_instruction, news_context_payload = None, None
                    log("News disabled for current show.")

            # C. Combine instructions
            combined_instructions = None
            instruction_parts = []

            # Show transition: announce the new show
            if is_show_transition and active_show:
                show_name = active_show.get("name", "")
                show_style = show_overrides.get("music_style", "")
                signation = show_overrides.get("signation")
                
                if signation:
                    # Signation track: DJ should announce the show and introduce
                    # this specific track (orchestrator will force-queue it)
                    transition_msg = (
                        f"SHOW TRANSITION: A new show is starting now! The show is called \"{show_name}\". "
                        f"Please announce the show name and its theme to the listeners. "
                        f"The opening track is \"{signation}\" — introduce it as the show's signature opening."
                    )
                    show_signation_track = signation
                    log(f"Show signation: {signation}")
                else:
                    transition_msg = (
                        f"SHOW TRANSITION: A new show is starting now! The show is called \"{show_name}\". "
                        f"Please announce the show name and its theme to the listeners, "
                        f"then suggest a fitting opening track."
                    )
                instruction_parts.append(transition_msg)

            # Show-specific music style instruction
            if show_overrides["music_style"]:
                instruction_parts.append(f"SHOW MUSIC DIRECTIVE: {show_overrides['music_style']}")
            
            # Show-specific DJ personality override
            if show_overrides["dj_personality"]:
                instruction_parts.append(f"DJ STYLE FOR THIS SHOW: {show_overrides['dj_personality']}")
            if weather_instruction:
                instruction_parts.append(weather_instruction)
            if news_instruction:
                instruction_parts.append(news_instruction)
            if instruction_parts:
                combined_instructions = "\n\n---\n\n".join(instruction_parts)

            # D. Prepare request data
            last_track_path = read_last_line(QUEUE_FILE)
            if last_track_path and not last_track_path.endswith(".mp3"):
                 last_track_path = None
            
            if last_track_path:
                last_track_name = os.path.basename(last_track_path)
            else:
                last_track_name = "Unknown track (Queue may have been empty)"

            # B2. Charts Context — check if the last played track is on the charts
            charts_instruction = None
            try:
                charts_lib = load_json(str(CHARTS_LIBRARY_FILE))
                if charts_lib and last_track_name:
                    # Match by basename without extension
                    last_base = os.path.splitext(last_track_name)[0]
                    for chart_song, position in charts_lib.items():
                        if chart_song.lower() == last_base.lower():
                            charts_instruction = (
                                f"The song that just played, \"{last_base}\", is currently at "
                                f"#{position} in the Austrian Singles Charts! "
                                f"You may mention this to the listeners."
                            )
                            log(f"Charts context: last track is at #{position} in the charts.")
                            break
            except Exception as e:
                log(f"Charts lookup error (non-fatal): {e}")
            if charts_instruction:
                instruction_parts.append(charts_instruction)
                combined_instructions = "\n\n---\n\n".join(instruction_parts)

            request_data = {
                "last_track": last_track_name,
                "listener_input": listener_input,
                "instructions": combined_instructions
            }
            
            # Track news deep dive for post-processing
            mark_id = None
            if news_context_payload and isinstance(news_context_payload, str):
                 mark_id = news_context_payload
                 log(f"Deep dive story queued for marking after success: {mark_id}")
                 request_data["instructions"] += f"\n__NEWS_ID_TO_MARK__: {mark_id}"
            
            # --- PHASE 2: DJ EXECUTION & SONG SELECTION ---
            # Load playlist once for the entire cycle
            playlist = []
            try:
                with open(str(PLAYLIST_FILE), 'r', encoding='utf-8') as f:
                    playlist = [line.strip() for line in f if line.strip()]
            except FileNotFoundError:
                log(f"CRITICAL: Playlist file not found at {PLAYLIST_FILE}")
                time.sleep(POLL_INTERVAL)
                continue

            dj_output = None
            success = False
            retry_count = 0
            
            while retry_count < MAX_DJ_ATTEMPTS and not success:
                retry_count += 1
                log(f"--- DJ Attempt {retry_count}/{MAX_DJ_ATTEMPTS} ---")
                
                dj_output = trigger_dj(request_data["last_track"], request_data["listener_input"], request_data["instructions"])

                if dj_output:
                    suggested_track = dj_output.get("track")
                    announcement_text = dj_output.get("announcement")
                    
                    # --- SIGNATION OVERRIDE ---
                    # If this is a show transition with a signation, use the DJ's
                    # announcement but force the signation track instead.
                    if show_signation_track and announcement_text:
                        log(f"SIGNATION: Overriding DJ track with show signation: {show_signation_track}")
                        cleaned_sig = clean_suggestion_for_matching(show_signation_track)
                        sig_found = None
                        for p_track in playlist:
                            if cleaned_sig.lower() in os.path.basename(p_track).lower():
                                sig_found = p_track
                                break
                        if sig_found:
                            announcement_audio_path = generate_announcement_audio(announcement_text)
                            if announcement_audio_path:
                                append_to_queue(str(announcement_audio_path))
                            else:
                                log("TTS failed — queueing signation without announcement.")
                            append_to_queue(sig_found)
                            last_track_played = sig_found
                            log(f"SIGNATION queued: {os.path.basename(sig_found)}")
                            show_signation_track = None  # consumed
                            success = True
                            continue
                        else:
                            log(f"SIGNATION track not found in library: {show_signation_track}. Falling through to normal flow.")
                            show_signation_track = None
                    
                    if suggested_track and announcement_text:
                        # --- HISTORY CHECK & VALIDATION START ---
                        
                        history = load_json(str(HISTORY_FILE))
                        # Skip the most recent entry — it's the one the DJ just suggested
                        recent_tracks = [entry["track"].lower() for entry in history[:-1] if "track" in entry]
                        
                        rejected_by_history = False
                        if suggested_track.lower() in recent_tracks:
                            log(f"DJ Suggestion REJECTED: '{suggested_track}' is in recent history.")
                            found_track = None
                            rejected_by_history = True
                        else:
                            # --- MUSIC MATCHING LOGIC START ---
                            # Priority 1: Try exact match with the raw DJ suggestion
                            # (preserves feat. tags, parentheses, etc.)
                            found_track = None
                            raw_lower = suggested_track.lower()
                            for p_track in playlist:
                                p_filename = os.path.basename(p_track)
                                if raw_lower in p_filename.lower():
                                    found_track = p_track
                                    log(f"Exact (raw) match found: {p_filename}")
                                    break
                            
                            # Priority 2: Try alias-based match
                            if not found_track:
                                alias_variants = apply_track_aliases(suggested_track)
                                for variant in alias_variants:
                                    variant_lower = variant.lower()
                                    for p_track in playlist:
                                        if variant_lower in os.path.basename(p_track).lower():
                                            found_track = p_track
                                            log(f"Alias match found: {os.path.basename(p_track)}")
                                            break
                                    if found_track:
                                        break
                            
                            # Priority 3: Try cleaned/fuzzy match if exact and alias didn't work
                            if not found_track:
                                potential_matches = []
                                cleaned_suggestion = clean_suggestion_for_matching(suggested_track)
                                
                                for p_track in playlist:
                                    p_filename = os.path.basename(p_track)
                                    p_filename_lower = p_filename.lower()
                                    
                                    if cleaned_suggestion.lower() in p_filename_lower:
                                        is_exact_version_match = suggested_track.lower() in p_filename_lower
                                        length_diff = len(p_filename_lower) - len(cleaned_suggestion.lower())
                                        potential_matches.append((p_track, p_filename, length_diff, is_exact_version_match))
                                
                                if potential_matches:
                                    potential_matches.sort(key=lambda x: (not x[3], x[2])) 
                                    found_track = potential_matches[0][0]
                            
                            # --- MUSIC MATCHING LOGIC END ---

                        if found_track:
                            # SUCCESS PATH: Track found! Generate audio and queue.
                            log(f"SUCCESS: Found track: {suggested_track}")
                            announcement_audio_path = generate_announcement_audio(announcement_text)

                            if announcement_audio_path:
                                append_to_queue(str(announcement_audio_path))
                            else:
                                log("TTS failed — queueing track without announcement.")
                            
                            append_to_queue(found_track)
                            last_track_played = found_track
                            
                            # Remove from suggestion pool if it came from there
                            show_pool_path = str(BASE_DIR / show_overrides["suggestion_pool"]) if show_overrides.get("suggestion_pool") else str(SUGGESTION_POOL_FILE)
                            remove_from_pool_file(show_pool_path, os.path.basename(found_track))
                            
                            # Mark news story as presented if this was a deep dive
                            if mark_id:
                                news_mark_presented(mark_id)
                                mark_id = None
                            
                            success = True
                        else:
                            # FALLBACK PATH 1: Track not found or rejected by history
                            log(f"Track NOT FOUND or REJECTED: {suggested_track}")
                            if not rejected_by_history:
                                append_to_wishlist(suggested_track)
                            
                            # --- NEWS-RELEVANT TRACKS ---
                            news_relevant = find_news_relevant_tracks(combined_instructions, playlist)
                            news_suggestion_lines = []
                            if news_relevant:
                                news_suggestion_lines = [
                                    os.path.splitext(os.path.basename(t))[0] + f"  (matches news quote: \"{q}\")"
                                    for t, q in news_relevant
                                ]
                                log(f"Adding {len(news_suggestion_lines)} news-relevant track suggestions.")
                            
                            # --- SUGGESTION POOL FALLBACK (Priority 1) ---
                            show_pool_file = str(BASE_DIR / show_overrides["suggestion_pool"]) if show_overrides.get("suggestion_pool") else None
                            pool_suggestions = get_pool_suggestions(pool_file=show_pool_file)
                            if news_suggestion_lines or pool_suggestions:
                                all_suggestions = []
                                if news_suggestion_lines:
                                    all_suggestions.append("NEWS-RELEVANT TRACKS (these match today's news — strongly prefer these if they fit the story):")
                                    all_suggestions.extend(news_suggestion_lines)
                                    all_suggestions.append("")
                                if pool_suggestions:
                                    all_suggestions.append("OTHER RECOMMENDED TRACKS (from most to least recommended):")
                                    all_suggestions.extend(pool_suggestions)
                                suggestion_list = "\n".join(all_suggestions)
                                retry_instructions = (
                                    f"The track '{suggested_track}' was unavailable. "
                                    f"Please select one of the following tracks instead:\n{suggestion_list}"
                                )
                                instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                log(f"Offering {len(pool_suggestions)} tracks from suggestion pool.")
                                request_data["instructions"] = instructions
                            else:
                                # --- ARTIST ALTERNATIVES FALLBACK (Priority 2) ---
                                artist = parse_artist_from_suggestion(suggested_track)
                                
                                if artist:
                                    alternatives = find_artist_alternatives(artist, playlist)
                                    
                                    if alternatives:
                                        alternative_list = "\n".join(os.path.basename(t) for t in alternatives[:MAX_ARTIST_SUGGESTIONS])
                                        retry_instructions = (
                                            f"The track '{suggested_track}' was unavailable. "
                                            f"Please select one of the following {len(alternatives)} available tracks by the same artist: {artist}. "
                                            f"Available tracks include: {alternative_list[:500]}..."
                                        )
                                        instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                        log(f"Alternatives found. Setting instructions for next attempt.")
                                        request_data["instructions"] = instructions
                                    else:
                                        if request_data["listener_input"]:
                                            retry_instructions = (
                                                f"The track '{suggested_track}' by {artist} was requested by a listener but is unavailable in the library. "
                                                "Please select a track by a COMPLETELY DIFFERENT artist, acknowledging the listener's general request if possible."
                                            )
                                            instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                            log(f"Listener request failed for {artist}. Setting instruction to re-prompt DJ.")
                                            request_data["instructions"] = instructions
                                        else:
                                            log(f"No alternatives found for artist: {artist}. Forcing new artist selection.")
                                            retry_instructions = f"The suggested artist {artist} has no available tracks. Please select a track by a completely different artist entirely."
                                            instructions = f"{combined_instructions}\n{retry_instructions}" if combined_instructions else retry_instructions
                                            request_data["instructions"] = instructions
                                else:
                                    log("Could not parse artist from suggestion. Falling back to pool.")
                                    fallback_track = fallback_queue_from_pool(show_overrides, playlist)
                                    if fallback_track:
                                        last_track_played = fallback_track
                                    success = True
                    else:
                        log("DJ response incomplete (missing track/announcement). Falling back to pool.")
                        fallback_track = fallback_queue_from_pool(show_overrides, playlist)
                        if fallback_track:
                            last_track_played = fallback_track
                        success = True
                else:
                    log("DJ cycle triggered, but no valid response. Falling back to pool.")
                    fallback_track = fallback_queue_from_pool(show_overrides, playlist)
                    if fallback_track:
                        last_track_played = fallback_track
                    success = True
            
            # If all DJ attempts exhausted without success, fall back to pool
            if not success:
                log(f"All {MAX_DJ_ATTEMPTS} DJ attempts exhausted. Falling back to pool.")
                fallback_track = fallback_queue_from_pool(show_overrides, playlist)
                if fallback_track:
                    last_track_played = fallback_track

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()