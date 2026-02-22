#!/usr/bin/env python3
"""
DJ Song Report -- Analyzes orchestrator.log to show what the DJ suggested
vs. what came from suggestion pools.

Usage:
    python dj_report.py --from "2026-02-22 06:00" --to "2026-02-22 09:00"
    python dj_report.py --from "2026-02-22 06:00" --to "2026-02-22 09:00" --show "Good morning Vienna!"
    python dj_report.py --from "2026-02-22" --to "2026-02-23"
    python dj_report.py --show "The blessings"  # uses full log

Partial dates like "2026-02-22" are treated as "2026-02-22 00:00:00".
"""

import argparse
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent / "orchestrator.log"

# Regex patterns
RE_TIMESTAMP = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]')
RE_ACTIVE_SHOW = re.compile(r'Active show: (.+)')
RE_ATTEMPT = re.compile(r'--- DJ Attempt (\d+)/\d+ ---')
RE_DJ_SUGGESTION = re.compile(r'^DJ Suggestion: (.+)$')
RE_SUCCESS = re.compile(r'SUCCESS: Found track: (.+)')
RE_REJECTED = re.compile(r'DJ Suggestion REJECTED: \'(.+?)\' is in recent history')
RE_NOT_FOUND = re.compile(r'Track NOT FOUND or REJECTED: (.+)')
RE_REMOVED_POOL = re.compile(r'Removed from pool (.+?): (.+)')
RE_REMOVED_POOL_OLD = re.compile(r'Removed from suggestion pool: (.+)')
RE_OFFERING = re.compile(r'Offering (\d+) tracks from suggestion pool')
RE_SHOW_TRANSITION = re.compile(r'SHOW TRANSITION:.*?-> \'(\w+)\' \((.+?)\)')
RE_OTHER_RECOMMENDED = re.compile(r'^OTHER RECOMMENDED TRACKS ')
RE_NEWS_RELEVANT = re.compile(r'^NEWS-RELEVANT TRACKS ')
RE_NEWS_QUOTE_SUFFIX = re.compile(r'\s+\(matches news quote:.*\)\s*$')


def parse_timestamp(ts_str):
    """Parse timestamp string, accepting partial dates."""
    ts_str = ts_str.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {ts_str}")


def parse_log(log_path, time_from=None, time_to=None, show_filter=None):
    """
    Parse the orchestrator log and extract DJ suggestion events.

    Returns:
        dj_own: dict {track: {"accepted": int, "rejected": int}}
        pool_picked: dict {track: int}  -- picked from pool
        offered_tracks: dict {track: int}  -- times offered to DJ in pool listings
    """

    lines = []
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    current_ts = None
    current_show = None
    cycle_attempt = 0
    in_range = time_from is None
    show_matches = not show_filter  # if filtering, default to no match until a show is seen
    reading_offered = False  # currently reading pool track lines

    # Results
    dj_own = defaultdict(lambda: {"accepted": 0, "rejected": 0})
    pool_picked = defaultdict(int)
    offered_tracks = defaultdict(int)  # track -> times offered to DJ

    # Per-offering-block: collect tracks, then commit them
    current_offered_block = []

    def flush_offered_block():
        nonlocal current_offered_block
        if current_offered_block and show_matches:
            for t in current_offered_block:
                offered_tracks[t] += 1
        current_offered_block = []

    for line in lines:
        line = line.rstrip('\n')

        # Update timestamp
        ts_match = RE_TIMESTAMP.match(line)
        if ts_match:
            # If we were reading offered tracks, a timestamped line ends the block
            if reading_offered:
                flush_offered_block()
                reading_offered = False

            try:
                current_ts = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

            # Time range filtering
            if time_from and time_to:
                in_range = time_from <= current_ts < time_to
            elif time_from:
                in_range = current_ts >= time_from
            elif time_to:
                in_range = current_ts < time_to
            else:
                in_range = True

        if not in_range:
            if reading_offered:
                flush_offered_block()
                reading_offered = False
            continue

        # Active show
        m = RE_ACTIVE_SHOW.search(line)
        if m:
            current_show = m.group(1).strip()
            show_matches = (not show_filter) or (show_filter.lower() in current_show.lower())
            continue

        # Show transition
        m = RE_SHOW_TRANSITION.search(line)
        if m:
            current_show = m.group(2).strip()
            show_matches = (not show_filter) or (show_filter.lower() in current_show.lower())
            continue

        if not show_matches:
            if reading_offered:
                flush_offered_block()
                reading_offered = False
            continue

        # Check for offered track list headers
        stripped = line.lstrip()
        if RE_OTHER_RECOMMENDED.match(stripped) or RE_NEWS_RELEVANT.match(stripped):
            # Start reading offered tracks
            flush_offered_block()  # flush any previous block
            reading_offered = True
            continue

        # If reading offered tracks, non-timestamped non-empty lines are track names
        if reading_offered:
            if stripped == '' or stripped.startswith('['):
                # Empty line between sections or timestamp = possible end
                if RE_TIMESTAMP.match(stripped):
                    flush_offered_block()
                    reading_offered = False
                # Empty lines or section breaks within the offering block -- keep reading
                continue
            # It's a track line
            track_name = stripped
            # Remove news quote suffix if present
            track_name = RE_NEWS_QUOTE_SUFFIX.sub('', track_name).strip()
            if track_name:
                current_offered_block.append(track_name)
            continue

        # Attempt number
        m = RE_ATTEMPT.search(line)
        if m:
            cycle_attempt = int(m.group(1))
            continue

        # DJ Suggestion
        m = RE_DJ_SUGGESTION.match(stripped)
        if m:
            last_suggestion = m.group(1).strip()
            last_suggestion_attempt = cycle_attempt
            continue

        # Success
        m = RE_SUCCESS.search(line)
        if m:
            track = m.group(1).strip()
            # Check if attempt 1 (DJ own) -- will be reclassified if pool removal follows
            if cycle_attempt <= 1:
                dj_own[track]["accepted"] += 1
            else:
                pool_picked[track] += 1
            continue

        # Pool removal after success -> reclassify as pool pick if it was in dj_own
        m = RE_REMOVED_POOL.search(line)
        if not m:
            m = RE_REMOVED_POOL_OLD.search(line)
        if m:
            track = m.group(m.lastindex).strip()
            # If this track was just counted as dj_own, move it to pool_picked
            if track in dj_own and dj_own[track]["accepted"] > 0:
                dj_own[track]["accepted"] -= 1
                pool_picked[track] += 1
                if dj_own[track]["accepted"] == 0 and dj_own[track]["rejected"] == 0:
                    del dj_own[track]
            continue

        # Rejected / not found on attempt 1 = DJ own rejected
        m = RE_REJECTED.search(line)
        if not m:
            m = RE_NOT_FOUND.search(line)
        if m:
            track = m.group(1).strip()
            if cycle_attempt <= 1:
                dj_own[track]["rejected"] += 1
            # attempt 2+ rejections are pool interaction noise
            continue

    # Final flush
    if reading_offered:
        flush_offered_block()

    return dict(dj_own), dict(pool_picked), dict(offered_tracks)


def format_report(dj_own, pool_picked, offered_tracks, show_filter, time_from, time_to):
    """Format the report for display."""

    lines = []
    lines.append("=" * 70)
    lines.append("DJ SONG REPORT")
    lines.append("=" * 70)

    if time_from or time_to:
        tf = time_from.strftime("%Y-%m-%d %H:%M") if time_from else "start"
        tt = time_to.strftime("%Y-%m-%d %H:%M") if time_to else "end"
        lines.append(f"Time range: {tf} -> {tt}")

    if show_filter:
        lines.append(f"Show filter: {show_filter}")

    lines.append("")

    # === CATEGORY 1: DJ's own suggestions ===
    if dj_own:
        lines.append("-" * 70)
        lines.append("1. DJ'S OWN SUGGESTIONS (not from suggestion pool)")
        lines.append("   Songs the DJ came up with independently (attempt 1).")
        lines.append("   Ranked by total times suggested (most -> least).")
        lines.append("-" * 70)

        sorted_own = sorted(
            dj_own.items(),
            key=lambda x: x[1]["accepted"] + x[1]["rejected"],
            reverse=True
        )
        for i, (track, info) in enumerate(sorted_own, 1):
            total = info["accepted"] + info["rejected"]
            status_parts = []
            if info["accepted"]:
                status_parts.append(f'{info["accepted"]}x accepted')
            if info["rejected"]:
                status_parts.append(f'{info["rejected"]}x rejected/not found')
            status = ", ".join(status_parts)
            lines.append(f"   {i:3}. {track}  ({total}x suggested: {status})")

        total_suggestions = sum(v["accepted"] + v["rejected"] for v in dj_own.values())
        lines.append(f"\n   Total: {len(sorted_own)} unique tracks, "
                     f"{total_suggestions} suggestions")
    else:
        lines.append("-" * 70)
        lines.append("1. DJ'S OWN SUGGESTIONS -- (none)")
        lines.append("-" * 70)

    lines.append("")

    # === CATEGORY 2: Picked from suggestion pool ===
    if pool_picked:
        lines.append("-" * 70)
        lines.append("2. SONGS PICKED FROM THE SUGGESTION POOL")
        lines.append("   DJ chose these from the offered pool/news tracks.")
        lines.append("   Ranked by times offered (least -> most, since fewer")
        lines.append("   appearances = fewer chances for the DJ to pick them).")
        lines.append("-" * 70)

        # Rank by how often they appeared in offerings (least first)
        sorted_pool = sorted(
            pool_picked.items(),
            key=lambda x: offered_tracks.get(x[0], 0)
        )
        for i, (track, count) in enumerate(sorted_pool, 1):
            times_offered = offered_tracks.get(track, 0)
            lines.append(f"   {i:3}. {track}  ({count}x picked, offered {times_offered}x)")

        lines.append(f"\n   Total: {len(sorted_pool)} unique tracks picked from pool")
    else:
        lines.append("-" * 70)
        lines.append("2. SONGS PICKED FROM THE SUGGESTION POOL -- (none)")
        lines.append("-" * 70)

    lines.append("")

    # === CATEGORY 3: Offered but not picked ===
    # All tracks that appeared in offering blocks but were never in pool_picked or dj_own
    picked_set = set(pool_picked.keys()) | set(dj_own.keys())
    not_picked = {t: c for t, c in offered_tracks.items() if t not in picked_set}

    if not_picked:
        lines.append("-" * 70)
        lines.append("3. POOL SONGS OFFERED BUT NOT PICKED BY THE DJ")
        lines.append("   These tracks were offered to the DJ in the suggestion")
        lines.append("   pool but the DJ never chose them.")
        lines.append("   Ranked by times offered (least -> most, since fewer")
        lines.append("   appearances = fewer chances for the DJ to pick them).")
        lines.append("-" * 70)

        sorted_not = sorted(not_picked.items(), key=lambda x: x[1])
        for i, (track, count) in enumerate(sorted_not, 1):
            lines.append(f"   {i:3}. {track}  (offered {count}x)")

        lines.append(f"\n   Total: {len(sorted_not)} tracks offered but not picked")
    else:
        lines.append("-" * 70)
        lines.append("3. POOL SONGS OFFERED BUT NOT PICKED -- (none)")
        lines.append("-" * 70)

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="DJ Song Report -- Analyze what the DJ suggested vs. what came from pools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dj_report.py --from "2026-02-22 06:00" --to "2026-02-22 09:00"
  python dj_report.py --show "Good morning Vienna!"
  python dj_report.py --from "2026-02-21 20:00" --to "2026-02-22" --show "blessings"
  python dj_report.py  # full log, all shows
        """
    )
    parser.add_argument("--from", dest="time_from", help="Start time (YYYY-MM-DD [HH:MM[:SS]])")
    parser.add_argument("--to", dest="time_to", help="End time (YYYY-MM-DD [HH:MM[:SS]])")
    parser.add_argument("--show", dest="show", help="Filter by show name (partial match, case-insensitive)")
    parser.add_argument("--log", dest="log_file", default=str(LOG_FILE), help="Path to orchestrator.log")

    args = parser.parse_args()

    time_from = parse_timestamp(args.time_from) if args.time_from else None
    time_to = parse_timestamp(args.time_to) if args.time_to else None

    dj_own, pool_picked, offered_tracks = parse_log(
        args.log_file, time_from, time_to, args.show
    )

    report = format_report(dj_own, pool_picked, offered_tracks, args.show, time_from, time_to)
    print(report)


if __name__ == "__main__":
    main()
