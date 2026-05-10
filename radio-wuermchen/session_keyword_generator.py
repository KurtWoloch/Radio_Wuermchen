"""
Session Keyword Generator for Radio Würmchen.

Extracts keywords from three sources with a quota system:
- News: up to 8 slots, min_count=1 (all unblocked words, most topical)
- Weather: up to 3 slots, min_count=2 (needs repetition to filter noise)
- Session: up to 4 slots, min_count=2 (conversation context)

Combined max: 15 keywords. Called by the DJ Orchestrator before each
song selection cycle.

Algorithm:
1. Find newest direct-chat session (chatType=direct in sessions.json)
2. Skip if keywords.txt is newer than session file (unless news/weather provided)
3. Extract from each source with its quota and frequency threshold
4. Combine: News + Weather + Session (dedup, preserve order)
5. Write to keywords.txt
"""

import json
import os
import re
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
SESSIONS_DIR = Path(r'C:\Users\kurt_\.openclaw\agents\main\sessions')
SESSIONS_JSON = SESSIONS_DIR / 'sessions.json'
KEYWORDS_FILE = BASE_DIR / 'keywords.txt'
BLOCKLIST_FILE = BASE_DIR / 'keywords_blocklist.txt'

# Quota system
NEWS_MAX = 8
NEWS_MIN_COUNT = 1
WEATHER_MAX = 3
WEATHER_MIN_COUNT = 2
SESSION_MAX = 4
SESSION_MIN_COUNT = 2
COMBINED_MAX = 15

# Session analysis: stop when distinct/total ratio drops below this
TARGET_RATIO = 0.633  # 63.3%


def load_blocklist():
    """Load words to exclude from analysis."""
    try:
        with open(BLOCKLIST_FILE, 'r', encoding='utf-8') as f:
            words = [line.strip().lower() for line in f
                     if line.strip() and not line.strip().startswith('#')]
        return set(words)
    except FileNotFoundError:
        return set()


def tokenize(text):
    """Split text into lowercase words, minimum 3 characters."""
    # Remove URLs and file paths
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[A-Z]:[\\/]\S+', '', text)
    # Extract words (letters only, min 3 chars, includes German umlauts and ß)
    words = re.findall(r'[a-zäöüß][a-zäöüß]{2,}', text.lower())
    return words


def find_newest_direct_session():
    """Find the newest direct-chat session file path. Returns (key, filepath) or None."""
    try:
        with open(SESSIONS_JSON, 'r', encoding='utf-8') as f:
            sessions = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    direct_sessions = []
    for key, sess in sessions.items():
        if sess.get('chatType') != 'direct':
            continue
        sf = sess.get('sessionFile', '')
        if sf and os.path.exists(sf):
            direct_sessions.append({
                'key': key,
                'file': sf,
                'updatedAt': sess.get('updatedAt', 0),
            })

    if not direct_sessions:
        return None

    direct_sessions.sort(key=lambda x: x['updatedAt'], reverse=True)
    best = direct_sessions[0]
    return (best['key'], best['file'])


def extract_message_texts(session_file):
    """
    Extract user+assistant text from a JSONL session file.
    Returns list of message texts in file order (oldest first).
    We'll reverse to get newest first.
    """
    messages = []

    with open(session_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get('type') != 'message':
                continue

            msg = entry.get('message', {})
            role = msg.get('role', '')
            if role not in ('user', 'assistant'):
                continue

            content = msg.get('content', [])
            if not isinstance(content, list):
                continue

            texts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    texts.append(item.get('text', ''))

            if texts:
                messages.append(' '.join(texts))

    return messages


def extract_source_keywords(text, blocklist, max_slots, min_count):
    """
    Extract keywords from a single source text.
    max_slots: max keywords to return
    min_count: minimum occurrence count to be eligible
    """
    if not text:
        return []

    words = [w for w in tokenize(text) if w not in blocklist]
    if not words:
        return []

    counter = Counter(words)

    # Take most common words meeting min_count, capped at max_slots
    keywords = [word for word, count in counter.most_common()
                if count >= min_count]

    return keywords[:max_slots]


def strip_news_wrapper(text):
    """Remove DJ prompt wrapper from news instruction, keep only news content.
    Handles both deep-dive (Headline:/Story: markers) and headline-segment formats."""
    if not text:
        return text

    # Deep dive format: "NEWS DEEP DIVE: ... Headline: X Story: Y ..."
    parts = []
    headline_match = re.search(r'Headline:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    if headline_match:
        parts.append(headline_match.group(1))

    story_match = re.search(r'Story:\s*(.+?)(?:\n\n|\nSummarize|\nPlease|$)', text, re.DOTALL | re.IGNORECASE)
    if story_match:
        parts.append(story_match.group(1))

    if parts:
        return ' '.join(parts)

    # Headlines format: "NEWS SEGMENT: ... \n\n{content}\n\nPlease present..."
    blocks = text.split('\n\n')
    if len(blocks) >= 3:
        middle = blocks[1]
        middle = re.sub(r'(?:Top stories|Also in the news|In brief|BREAKING NEWS):\s*', '', middle)
        return middle.strip()

    return text


def generate_keywords(news_text=None, weather_text=None):
    """
    Main entry point. Quota-based keyword generation:
    - News: up to 8, min_count=1
    - Weather: up to 3, min_count=2
    - Session: up to 4, min_count=2
    Combined: up to 15 (dedup, News > Weather > Session priority order).

    Returns list of keywords, or empty list if skipped.
    """
    blocklist = load_blocklist()

    # 1. Find newest direct session
    result = find_newest_direct_session()
    if not result:
        return []

    session_key, session_file = result

    # 2. Date check: skip if keywords.txt is newer than session file
    # (unless news/weather provided — those change every cycle)
    has_external = bool(news_text or weather_text)
    if os.path.exists(KEYWORDS_FILE) and not has_external:
        kw_mtime = os.path.getmtime(KEYWORDS_FILE)
        sess_mtime = os.path.getmtime(session_file)
        if kw_mtime >= sess_mtime:
            return []

    # 3. News keywords (up to NEWS_MAX, min_count=NEWS_MIN_COUNT)
    news_kw = extract_source_keywords(
        strip_news_wrapper(news_text), blocklist, NEWS_MAX, NEWS_MIN_COUNT
    )

    # 4. Weather keywords (up to WEATHER_MAX, min_count=WEATHER_MIN_COUNT)
    weather_kw = extract_source_keywords(
        weather_text, blocklist, WEATHER_MAX, WEATHER_MIN_COUNT
    )

    # 5. Session keywords (up to SESSION_MAX, min_count=SESSION_MIN_COUNT)
    session_kw = []
    all_messages = extract_message_texts(session_file)
    all_messages.reverse()  # newest first

    if all_messages:
        word_counter = Counter()
        messages_used = 0

        for msg_text in all_messages:
            words = [w for w in tokenize(msg_text) if w not in blocklist]

            if not words:
                messages_used += 1
                continue

            word_counter.update(words)
            messages_used += 1

            total = sum(word_counter.values())
            distinct = len(word_counter)
            ratio = distinct / total if total > 0 else 1.0

            if ratio <= TARGET_RATIO:
                break

        # Cap at SESSION_MAX
        session_kw = [word for word, _ in word_counter.most_common(SESSION_MAX)
                       if word_counter[word] >= SESSION_MIN_COUNT]

    # 6. Combine: News + Weather + Session (dedup, preserve order)
    seen = set()
    keywords = []
    for kw in news_kw + weather_kw + session_kw:
        if kw not in seen:
            seen.add(kw)
            keywords.append(kw)

    # Cap at COMBINED_MAX
    keywords = keywords[:COMBINED_MAX]

    # 7. Write keywords.txt
    if keywords:
        with open(KEYWORDS_FILE, 'w', encoding='utf-8') as f:
            f.write('# Quota-based keywords: News + Weather + Session\n')
            f.write(f'# Generated: {datetime.now().isoformat()}\n')
            f.write(f'# News: {len(news_kw)}/{NEWS_MAX} '
                    f'(min_count={NEWS_MIN_COUNT})\n')
            f.write(f'# Weather: {len(weather_kw)}/{WEATHER_MAX} '
                    f'(min_count={WEATHER_MIN_COUNT})\n')
            f.write(f'# Session: {len(session_kw)}/{SESSION_MAX} '
                    f'(min_count={SESSION_MIN_COUNT})\n')
            f.write(f'# Combined: {len(keywords)}/{COMBINED_MAX}\n')
            f.write(f'# Session file: {os.path.basename(session_file)}\n')
            for kw in keywords:
                f.write(kw + '\n')

    return keywords


# === CLI entry point ===
if __name__ == '__main__':
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    keywords = generate_keywords()
    if keywords:
        print(f"Generated {len(keywords)} keywords: {', '.join(keywords)}")
    else:
        print("No new keywords generated (up to date or no session data).")
