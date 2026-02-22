#!/usr/bin/env python3
"""
Pool Auto-Refill — Classifies unassigned library tracks into show suggestion pools
using the same Gemini LLM as the DJ brain.

Usage:
    python pool_refill.py                    # Dry run: classify 50 tracks, show results
    python pool_refill.py --apply            # Classify and add to pool files
    python pool_refill.py --batch-size 30    # Classify 30 tracks per LLM call
    python pool_refill.py --rounds 3         # Do 3 rounds of 50 (= 150 tracks)
    python pool_refill.py --rounds 3 --apply # Classify 150 tracks and apply

Each round picks a random batch of unassigned tracks, sends them to the LLM
with show descriptions, and classifies them. Results are logged to
pool_refill_log.json for review.
"""

import json
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PLAYLIST_FILE = SCRIPT_DIR / "music.playlist"
SCHEDULE_FILE = SCRIPT_DIR / "shows_schedule.json"
CONFIG_FILE = SCRIPT_DIR / "dj_config.json"
LOG_FILE = SCRIPT_DIR / "pool_refill_log.json"
PYTHON_BIN = r"C:\Program Files\Python311\python.exe"

DEFAULT_BATCH_SIZE = 50


def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_library_tracks():
    """Read playlist and extract 'Artist - Track' names."""
    tracks = []
    with open(PLAYLIST_FILE, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            basename = os.path.splitext(os.path.basename(line))[0]
            # Only include tracks with "Artist - Title" format
            if ' - ' in basename:
                tracks.append(basename)
    return tracks


def get_all_pool_tracks():
    """Read all suggestion_pool*.txt files and return a set of lowercased track names."""
    pooled = set()
    for pool_file in SCRIPT_DIR.glob("suggestion_pool*.txt"):
        try:
            with open(pool_file, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        pooled.add(line.lower())
        except Exception:
            pass
    return pooled


def get_shows():
    """Load show schedule and return list of {id, name, music_style, pool_file}."""
    data = load_json(SCHEDULE_FILE)
    shows = []
    for show in data.get("shows", []):
        ov = show.get("overrides", {})
        pool = ov.get("suggestion_pool", "")
        shows.append({
            "id": show["id"],
            "name": show["name"],
            "music_style": ov.get("music_style", ""),
            "pool_file": pool,
        })
    return shows


def build_prompt(shows, track_batch):
    """Build the system prompt and user message for classification."""
    show_descriptions = []
    for s in shows:
        show_descriptions.append(f'- "{s["name"]}" (id: {s["id"]}): {s["music_style"]}')
    show_list = "\n".join(show_descriptions)

    track_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(track_batch))

    system_prompt = (
        "You are a music classification assistant for Radio Wuermchen. "
        "Your task is to classify tracks into the show they fit best. "
        "Respond ONLY with a JSON array. Each element must be an object with exactly these keys:\n"
        '  "track": the track name exactly as given,\n'
        '  "show_id": the id of the best-fitting show (or "none" if no show fits),\n'
        '  "reason": a brief reason (max 15 words)\n'
        "Do not include any other text, markdown, or commentary. Just the JSON array."
    )

    user_message = (
        f"Here are the available shows:\n{show_list}\n\n"
        f"Classify each of these {len(track_batch)} tracks into the single best-fitting show. "
        f"If a track clearly doesn't fit ANY show, use show_id \"none\".\n\n"
        f"{track_list}"
    )

    return system_prompt, user_message


def call_llm(config, system_prompt, user_message):
    """Call Gemini API (same approach as dj_brain.py)."""
    try:
        from google import genai as genai_client
        from google.genai import types
    except ImportError:
        print("ERROR: google-genai package not installed.", file=sys.stderr)
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        return None

    try:
        client = genai_client.Client(api_key=api_key)
        model = config.get("model", "gemini-2.5-flash")
        print(f"  Calling {model}...")

        response = client.models.generate_content(
            model=model,
            contents=[system_prompt, user_message],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],
                temperature=0.3  # Lower temperature for more consistent classification
            )
        )

        if not response.candidates or not response.candidates[0].content.parts:
            print(f"  API Response Empty: {response.prompt_feedback}", file=sys.stderr)
            return None

        return response.candidates[0].content.parts[0].text
    except Exception as e:
        print(f"  Gemini API Error: {e}", file=sys.stderr)
        return None


def parse_llm_response(raw_text):
    """Extract the JSON array from the LLM response."""
    # Strip markdown code fences if present
    text = raw_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in the text
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    print(f"  Failed to parse LLM response as JSON.", file=sys.stderr)
    print(f"  Raw response (first 500 chars): {raw_text[:500]}", file=sys.stderr)
    return None


def detect_file_encoding(path):
    """Detect whether a file is UTF-8 or Latin-1/ANSI."""
    try:
        with open(path, 'rb') as f:
            raw = f.read()
        if raw[:3] == b'\xef\xbb\xbf':
            return 'utf-8-sig'
        try:
            raw.decode('utf-8')
            # If it's pure ASCII or valid UTF-8 with high bytes, call it UTF-8
            if any(b > 127 for b in raw):
                return 'utf-8'
            # Pure ASCII — match whatever we'd write (default to latin-1 to be safe)
            return 'latin-1'
        except UnicodeDecodeError:
            return 'latin-1'
    except FileNotFoundError:
        return 'utf-8'


def append_to_pool(pool_file_path, track_name):
    """Append a track to a pool file, matching the file's existing encoding."""
    enc = detect_file_encoding(pool_file_path)
    with open(pool_file_path, 'a', encoding=enc) as f:
        f.write(track_name + '\n')


def load_log():
    """Load the refill log."""
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return {"runs": [], "classified": {}}


def save_log(log_data):
    """Save the refill log."""
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Classify unassigned library tracks into show suggestion pools via LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pool_refill.py                     # Dry run: classify 50 tracks
  python pool_refill.py --apply             # Classify and write to pools
  python pool_refill.py --rounds 5 --apply  # 5 rounds of 50 = 250 tracks
  python pool_refill.py --batch-size 30     # 30 tracks per LLM call
        """
    )
    parser.add_argument("--apply", action="store_true", help="Actually write to pool files (default: dry run)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help=f"Tracks per LLM call (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--rounds", type=int, default=1, help="Number of rounds (default: 1)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible runs")

    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    # Load data
    config = load_json(CONFIG_FILE)
    shows = get_shows()
    if not shows:
        print("ERROR: No shows found in shows_schedule.json")
        sys.exit(1)

    print(f"Loaded {len(shows)} shows:")
    for s in shows:
        print(f"  {s['id']:20s} {s['name']}")
    print()

    library = get_library_tracks()
    pooled = get_all_pool_tracks()
    log_data = load_log()
    previously_classified = set(log_data.get("classified", {}).keys())

    # Filter: not in any pool AND not previously classified
    unassigned = [t for t in library
                  if t.lower() not in pooled
                  and t.lower() not in previously_classified]

    # Deduplicate
    seen = set()
    unique_unassigned = []
    for t in unassigned:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            unique_unassigned.append(t)

    print(f"Library: {len(library)} tracks")
    print(f"Already in pools: {len(pooled)} tracks")
    print(f"Previously classified: {len(previously_classified)} tracks")
    print(f"Unassigned & unclassified: {len(unique_unassigned)} tracks")
    print()

    if not unique_unassigned:
        print("Nothing to classify!")
        return

    # Build show id -> pool file mapping
    show_pool_map = {}
    show_name_map = {}
    for s in shows:
        show_pool_map[s["id"]] = str(SCRIPT_DIR / s["pool_file"]) if s["pool_file"] else None
        show_name_map[s["id"]] = s["name"]

    # Default pool for "none" tracks (from schedule defaults)
    schedule_data = load_json(SCHEDULE_FILE)
    default_pool = schedule_data.get("defaults", {}).get("suggestion_pool", "")
    default_pool_path = str(SCRIPT_DIR / default_pool) if default_pool else None
    if default_pool:
        print(f"Default pool for unclassified tracks: {default_pool}")
        print()

    total_classified = 0
    total_added = 0
    total_none = 0

    for round_num in range(1, args.rounds + 1):
        # Re-filter in case previous round added tracks
        if round_num > 1:
            already = set(log_data.get("classified", {}).keys())
            unique_unassigned = [t for t in unique_unassigned if t.lower() not in already]

        if not unique_unassigned:
            print(f"Round {round_num}: No more tracks to classify.")
            break

        batch = random.sample(unique_unassigned, min(args.batch_size, len(unique_unassigned)))
        print(f"--- Round {round_num}/{args.rounds}: classifying {len(batch)} tracks ---")

        system_prompt, user_message = build_prompt(shows, batch)
        raw_response = call_llm(config, system_prompt, user_message)

        if not raw_response:
            print("  LLM call failed. Skipping round.")
            continue

        classifications = parse_llm_response(raw_response)
        if not classifications:
            print("  Failed to parse response. Skipping round.")
            continue

        # Process results
        run_results = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "round": round_num,
            "batch_size": len(batch),
            "applied": args.apply,
            "results": []
        }

        for item in classifications:
            track = item.get("track", "").strip()
            show_id = item.get("show_id", "none").strip()
            reason = item.get("reason", "").strip()

            if not track:
                continue

            result_entry = {
                "track": track,
                "show_id": show_id,
                "show_name": show_name_map.get(show_id, "none"),
                "reason": reason
            }

            if show_id != "none" and show_id in show_pool_map:
                pool_path = show_pool_map[show_id]
                if pool_path and args.apply:
                    append_to_pool(pool_path, track)
                    total_added += 1
                    result_entry["action"] = "added"
                else:
                    result_entry["action"] = "would_add" if pool_path else "no_pool_file"
                total_classified += 1
            else:
                # Route "none" tracks to the default pool
                if default_pool_path and args.apply:
                    append_to_pool(default_pool_path, track)
                    total_added += 1
                    result_entry["action"] = "added_default"
                else:
                    result_entry["action"] = "would_add_default" if default_pool_path else "none"
                total_none += 1

            run_results["results"].append(result_entry)

            # Record in classified map
            if "classified" not in log_data:
                log_data["classified"] = {}
            log_data["classified"][track.lower()] = {
                "show_id": show_id,
                "reason": reason,
                "timestamp": run_results["timestamp"]
            }

        log_data["runs"].append(run_results)
        save_log(log_data)

        # Print summary for this round
        show_counts = {}
        none_tracks = []
        for r in run_results["results"]:
            if r["show_id"] == "none":
                none_tracks.append(r)
            else:
                show_counts[r["show_name"]] = show_counts.get(r["show_name"], 0) + 1

        print(f"  Classified: {len(run_results['results'])} tracks")
        for show_name, count in sorted(show_counts.items(), key=lambda x: -x[1]):
            print(f"    {show_name}: {count}")
        if none_tracks:
            pool_label = f"default pool ({default_pool})" if default_pool else "no show"
            print(f"    -> {pool_label}: {len(none_tracks)}")
            for nt in none_tracks[:5]:
                print(f"      - {nt['track']}  ({nt['reason']})")
            if len(none_tracks) > 5:
                print(f"      ... and {len(none_tracks) - 5} more")
        print()

    # Final summary
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"{'=' * 50}")
    print(f"DONE ({mode})")
    print(f"  Tracks classified into shows: {total_classified}")
    print(f"  Tracks added to pools: {total_added}")
    print(f"  Tracks matching no show (-> default pool): {total_none}")
    print(f"  Log saved to: {LOG_FILE.name}")
    if not args.apply and total_classified > 0:
        print(f"\n  Run with --apply to write to pool files.")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
