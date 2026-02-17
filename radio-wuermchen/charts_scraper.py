"""
Charts Scraper for Radio Würmchen
Scrapes the Austrian Singles Top 75 from austriancharts.at
and rebuilds the "Music for Young People" suggestion pool with
chart entries prioritized at the top (descending from 75 to 1).

Run daily; only triggers pool regeneration when charts have changed.
"""
import os
import re
import json
import subprocess
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHARTS_URL = "https://austriancharts.at/charts/singles"
CHARTS_CACHE_FILE = os.path.join(SCRIPT_DIR, "charts_cache.json")
CHARTS_LIBRARY_FILE = os.path.join(SCRIPT_DIR, "charts_in_library.json")
PLAYLIST_FILE = os.path.join(SCRIPT_DIR, "music.playlist")
POOL_MODERN_FILE = os.path.join(SCRIPT_DIR, "suggestion_pool_modern.txt")


def fetch_charts_html():
    """Fetch the Austrian charts page HTML."""
    req = urllib.request.Request(CHARTS_URL, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Radio-Wuermchen/1.0"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_charts(html):
    """Parse chart entries from HTML. Returns (date_str, list of entries).
    Each entry: {position, previous, artist, title}
    """
    # Extract chart date
    date_match = re.search(r"Singles Top 75\s+(\d{2}\.\d{2}\.\d{4})", html)
    chart_date = date_match.group(1) if date_match else "unknown"

    entries = []
    # Split by chart rows
    rows = re.split(r'<tr class="charts">', html)[1:]

    for row in rows:
        # All td contents (non-greedy, but tds can contain nested tags)
        # Use a more robust approach: find each <td...>...</td> pair
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(tds) < 5:
            continue

        # td[0]: current position
        position_text = re.sub(r'<[^>]+>', '', tds[0]).strip()
        try:
            position = int(position_text)
        except ValueError:
            continue

        # td[1]: previous position — could be a number, "RE", or contain neu.gif
        prev_raw = tds[1]
        if 'neu.gif' in prev_raw:
            previous = "NEW"
        else:
            prev_text = re.sub(r'<[^>]+>', '', prev_raw).strip()
            previous = prev_text if prev_text else "?"

        # td[4]: contains <b>Artist</b><br>Title</a>
        info_td = tds[4]
        artist_match = re.search(r'<b>(.*?)</b>', info_td, re.DOTALL)
        title_match = re.search(r'<br\s*/?>\s*(.*?)</a>', info_td, re.DOTALL)

        if not artist_match or not title_match:
            continue

        artist = re.sub(r'<[^>]+>', '', artist_match.group(1)).strip()
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

        entries.append({
            "position": position,
            "previous": previous,
            "artist": artist,
            "title": title,
        })

    return chart_date, entries


def load_cached_charts():
    """Load previously cached chart data."""
    if not os.path.exists(CHARTS_CACHE_FILE):
        return None
    try:
        with open(CHARTS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_charts_cache(chart_date, entries):
    """Save chart data to cache."""
    with open(CHARTS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": chart_date, "entries": entries}, f, indent=2, ensure_ascii=False)


def charts_changed(chart_date, cached):
    """Check if the charts have changed since last scrape."""
    if cached is None:
        return True
    return cached.get("date") != chart_date


def load_playlist():
    """Load the music library playlist."""
    with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def basename_no_ext(path):
    """Get filename without extension."""
    return os.path.splitext(os.path.basename(path))[0]


def find_chart_songs_in_library(entries, playlist):
    """Check each chart entry against the song library.
    Returns list of (basename, position) tuples in chart order (descending: 75->1).
    """
    # Build a lookup: lowercase basename -> original basename
    library_lookup = {}
    for track in playlist:
        bn = basename_no_ext(track)
        library_lookup[bn.lower()] = bn

    matched = []
    # Process in descending order (75 to 1)
    sorted_entries = sorted(entries, key=lambda e: e["position"], reverse=True)

    for entry in sorted_entries:
        artist = entry["artist"]
        title = entry["title"]
        position = entry["position"]
        # Try common filename patterns: "Artist - Title"
        candidates = [
            f"{artist} - {title}",
            f"{artist} - {title}".replace("/", " & "),  # feat. variations
        ]
        # Also try with "feat." removed from artist
        clean_artist = re.sub(r'\s*(feat\.|ft\.|featuring)\s+.*', '', artist, flags=re.IGNORECASE)
        if clean_artist != artist:
            candidates.append(f"{clean_artist} - {title}")

        found = False
        for candidate in candidates:
            if candidate.lower() in library_lookup:
                matched.append((library_lookup[candidate.lower()], position))
                found = True
                break
        if not found:
            # Fuzzy: check if any library entry starts with "Artist - Title" (case-insensitive)
            search_prefix = f"{artist} - {title}".lower()
            clean_search = f"{clean_artist} - {title}".lower()
            for lc_key, orig in library_lookup.items():
                if lc_key.startswith(search_prefix) or lc_key.startswith(clean_search):
                    matched.append((orig, position))
                    break

    return matched


def save_charts_in_library(chart_songs):
    """Save the chart songs found in library with their positions to a JSON file.
    chart_songs: list of (basename, position) tuples.
    """
    data = {song: position for song, position in chart_songs}
    with open(CHARTS_LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(data)} chart-library matches to {os.path.basename(CHARTS_LIBRARY_FILE)}")


def rebuild_modern_pool(chart_songs):
    """Rebuild suggestion_pool_modern.txt with chart songs on top,
    followed by the regular modern pool content.
    chart_songs: list of (basename, position) tuples.
    """
    # First, regenerate all pools via generate_pools.py
    print("Regenerating all suggestion pools...")
    generate_script = os.path.join(SCRIPT_DIR, "generate_pools.py")
    subprocess.run([sys.executable, generate_script], cwd=SCRIPT_DIR, check=True)
    print()

    # Read the freshly generated modern pool
    with open(POOL_MODERN_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    # Separate header from tracks
    header = "# Suggestion Pool: Music for Young People (2010s-2020s)"
    regular_tracks = [l for l in lines if not l.startswith("#")]

    # Remove any chart songs from the regular pool to avoid duplicates
    chart_set = set(s.lower() for s, _ in chart_songs)
    regular_tracks = [t for t in regular_tracks if t.lower() not in chart_set]

    # Write: header, then chart songs (75->1) with position annotations, then regular pool
    with open(POOL_MODERN_FILE, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        f.write(f"# --- Austrian Charts entries ({len(chart_songs)} found in library) ---\n")
        for song, position in chart_songs:
            f.write(f"{song} (currently at #{position} in the Austrian charts)\n")
        f.write("# --- Regular modern pool ---\n")
        for track in regular_tracks:
            f.write(track + "\n")

    print(f"Modern pool rebuilt: {len(chart_songs)} chart songs + {len(regular_tracks)} regular tracks")


def main():
    print("=== Austrian Charts Scraper ===")
    print(f"Fetching {CHARTS_URL}...")
    html = fetch_charts_html()

    chart_date, entries = parse_charts(html)
    print(f"Chart date: {chart_date}")
    print(f"Parsed {len(entries)} chart entries")

    if not entries:
        print("ERROR: No chart entries found! Page structure may have changed.")
        return

    # Print chart summary
    for e in entries[:5]:
        print(f"  #{e['position']} ({e['previous']}) {e['artist']} - {e['title']}")
    if len(entries) > 5:
        print(f"  ... ({len(entries) - 5} more)")

    # Check if charts changed
    cached = load_cached_charts()
    if not charts_changed(chart_date, cached):
        print(f"\nCharts unchanged (still {chart_date}). No action needed.")
        return

    print(f"\nCharts updated! (was: {cached['date'] if cached else 'none'} -> now: {chart_date})")

    # Save new charts
    save_charts_cache(chart_date, entries)

    # Find chart songs in library
    playlist = load_playlist()
    chart_songs = find_chart_songs_in_library(entries, playlist)
    print(f"\nFound {len(chart_songs)} chart songs in library (out of {len(entries)}):")
    for song, position in chart_songs:
        print(f"  * #{position} {song}")

    # Save chart-library mapping for the orchestrator
    save_charts_in_library(chart_songs)

    # Rebuild the modern pool
    rebuild_modern_pool(chart_songs)

    print("\nDone!")


if __name__ == "__main__":
    main()
