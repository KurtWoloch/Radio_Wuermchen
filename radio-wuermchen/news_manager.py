# News Manager for Radio Würmchen
#
# Scrapes orf.at main page and sub-story pages, caches results,
# tracks which stories are new and which have been presented.
#
# Commands:
#   python news_manager.py update          - Scrape main page, fetch new sub-stories
#   python news_manager.py headlines       - Get current top headlines (JSON to stdout)
#   python news_manager.py next_story      - Get next unpresented story for in-depth segment
#   python news_manager.py mark <story_id> - Mark a story as presented in depth
#   python news_manager.py status          - Show cache status
#
# Files:
#   news_cache.json      - Main cache: all stories, state, timestamps
#   news_substories.json - Cached sub-story descriptions (keyed by URL)

import json
import sys
import os
import re
import time
import hashlib
import urllib.request
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "news_cache.json")
SUBSTORY_CACHE = os.path.join(SCRIPT_DIR, "news_substories.json")
MAIN_URL = "https://www.orf.at"
CACHE_MAX_AGE = 3600  # 60 minutes

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# --- HELPERS ---

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or 'utf-8'
        return resp.read().decode(charset)

def clean_html(text):
    """Strip HTML tags, decode entities, clean whitespace."""
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?(h[1-6]|p|div|li|ul|ol)\b[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    text = text.replace('\u201e', '"').replace('\u201c', '"').replace('\u201d', '"')
    lines = [l.strip() for l in text.splitlines()]
    text = '\n'.join(l for l in lines if l)
    return text.strip()

def make_id(text):
    """Generate a short stable ID from text."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:10]


# --- MAIN PAGE PARSING ---

def parse_breaking_news(html):
    """Extract breaking news if present."""
    m = re.search(r'id="ticker-breaking-special"[^>]*>(.*?)</div>', html, re.DOTALL)
    if m:
        content = clean_html(m.group(1)).strip()
        if content:
            return content
    return None

def parse_top_stories(html):
    """Extract top stories from the picture grid section."""
    stories = []

    # Find the top area: from oon-grid to "close overflow wrapper"
    top_start = html.find('class="oon-grid oon-grid-alias-news"')
    top_end = html.find('close overflow wrapper', top_start if top_start >= 0 else 0)
    if top_start < 0 or top_end < 0:
        return stories

    top_html = html[top_start:top_end]

    # Each grid item has an <a href="..."> and then two oon-grid-texts-headline divs
    # We want the second one (without <br/> line breaks) for clean headlines
    # Pattern: find each <a href> followed by headline divs
    # Actually, looking at the structure: <a href="URL"> wraps the whole item,
    # and inside there are two headline divs. We want pairs of (URL, headline).

    # Find all grid items by their <a href> links within the grid
    items = re.finditer(
        r'<a\s+href="(https://[^"]+/stories/\d+/)"[^>]*>.*?</a>',
        top_html, re.DOTALL
    )

    seen_urls = set()
    for item_match in items:
        url = item_match.group(1)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        block = item_match.group(0)
        # Find all h1 tags in this block — take the last one (cleaner, no <br/>)
        h1s = re.findall(r'<h1>(.*?)</h1>', block, re.DOTALL)
        if h1s:
            headline = clean_html(h1s[-1]).strip()
            # Collapse any remaining newlines (from <br/> removal) into spaces
            headline = re.sub(r'\s+', ' ', headline)
            if headline:
                stories.append({
                    'id': make_id(url),
                    'headline': headline,
                    'url': url,
                    'type': 'top',
                    'has_story': True
                })

    return stories

def parse_regular_stories(html):
    """Extract regular ticker stories and quicklinks."""
    stories = []

    # Find all article elements
    for m in re.finditer(r'<article\s+class="ticker-story([^"]*)"[^>]*data-id="(\d+)"[^>]*>', html):
        classes = m.group(1)
        data_id = m.group(2)
        is_quicklink = 'quicklink' in classes

        # Find the end of this article
        art_start = m.end()
        art_end = html.find('</article>', art_start)
        if art_end < 0:
            continue
        article_html = html[art_start:art_end]

        # Extract headline
        headline = None
        h_match = re.search(r'class="ticker-story-headline"[^>]*>(.*?)</h3>', article_html, re.DOTALL)
        if h_match:
            # Headline contains an <a> tag
            a_match = re.search(r'<a[^>]*>(.*?)</a>', h_match.group(1), re.DOTALL)
            if a_match:
                headline = clean_html(a_match.group(1)).strip()

        if not headline:
            continue

        # Extract URL from headline link
        url = None
        url_match = re.search(r'ticker-story-headline.*?<a\s+href="([^"]+)"', article_html, re.DOTALL)
        if url_match:
            url = url_match.group(1)

        story_text = None
        if not is_quicklink:
            # Extract story text from story-story div, handling nested section/figure elements
            story_match = re.search(r'<div\s+class="story-story">(.*)', article_html, re.DOTALL)
            if story_match:
                story_text = extract_story_text(story_match.group(1))

        stories.append({
            'id': make_id(f"ticker-{data_id}"),
            'headline': headline,
            'url': url,
            'type': 'quicklink' if is_quicklink else 'regular',
            'story': story_text,
            'has_story': story_text is not None and len(story_text) > 20
        })

    return stories

def extract_story_text(html_after_story_div):
    """Extract text from story-story content, skipping section and figure elements."""
    result = []
    pos = 0
    text = html_after_story_div
    depth = 1  # We're already inside the story-story div

    while pos < len(text) and depth > 0:
        # Look for the next interesting tag
        next_tag = re.search(r'<(/?)(\w+)([^>]*)>', text[pos:])
        if not next_tag:
            # No more tags, grab remaining text
            result.append(text[pos:])
            break

        tag_start = pos + next_tag.start()
        tag_end = pos + next_tag.end()
        is_closing = next_tag.group(1) == '/'
        tag_name = next_tag.group(2).lower()
        tag_attrs = next_tag.group(3)

        # Grab text before this tag
        result.append(text[pos:tag_start])

        if not is_closing and tag_name in ('section', 'figure'):
            # Skip everything until matching closing tag
            close_tag = f'</{tag_name}>'
            close_pos = text.find(close_tag, tag_end)
            if close_pos >= 0:
                pos = close_pos + len(close_tag)
            else:
                pos = tag_end
            continue

        if is_closing and tag_name == 'div':
            depth -= 1
            if depth <= 0:
                break
            pos = tag_end
            continue

        if not is_closing and tag_name == 'div':
            depth += 1

        pos = tag_end

    raw = ''.join(result)
    return clean_html(raw)


# --- SUB-STORY FETCHING ---

def fetch_substory(url):
    """Fetch a sub-story page and extract headline + description from JSON-LD."""
    try:
        html = fetch_url(url, timeout=15)

        # Find JSON-LD block
        m = re.search(r'<script\s+type="application/ld\+json">\s*(\{.*?\})\s*</script>', html, re.DOTALL)
        if not m:
            return None

        data = json.loads(m.group(1))
        headline = data.get('headline', '')
        description = data.get('description', '')

        if description:
            return {
                'headline': headline,
                'description': description,
                'fetched_at': time.time()
            }
    except Exception as e:
        print(f"  Error fetching substory {url}: {e}", file=sys.stderr)
    return None


# --- CACHE MANAGEMENT ---

def load_cache():
    data = load_json(CACHE_FILE)
    if not data:
        data = {
            'last_update': 0,
            'stories': [],
            'presented': [],  # IDs of stories presented in depth
            'last_headlines_at': 0
        }
    return data

def save_cache(cache):
    save_json(CACHE_FILE, cache)

def load_substory_cache():
    return load_json(SUBSTORY_CACHE)

def save_substory_cache(data):
    save_json(SUBSTORY_CACHE, data)


# --- COMMANDS ---

def cmd_update():
    """Scrape main page, detect new stories, fetch sub-stories for top stories."""
    cache = load_cache()
    substories = load_substory_cache()

    # Check if cache is still fresh
    age = time.time() - cache.get('last_update', 0)
    if age < CACHE_MAX_AGE:
        print(f"Cache is fresh ({int(age)}s old, max {CACHE_MAX_AGE}s). Skipping update.")
        print(f"Stories in cache: {len(cache.get('stories', []))}")
        return cache

    print(f"Fetching {MAIN_URL}...")
    html = fetch_url(MAIN_URL)
    print(f"Fetched {len(html)} chars")

    # Parse all sections
    breaking = parse_breaking_news(html)
    top_stories = parse_top_stories(html)
    regular_stories = parse_regular_stories(html)

    print(f"Breaking: {'YES' if breaking else 'no'}")
    print(f"Top stories: {len(top_stories)}")
    print(f"Regular stories: {len(regular_stories)}")

    # Build new story list
    new_stories = []

    if breaking:
        new_stories.append({
            'id': make_id(f"breaking-{breaking[:50]}"),
            'headline': breaking,
            'url': None,
            'type': 'breaking',
            'has_story': False,
            'story': None
        })

    new_stories.extend(top_stories)
    new_stories.extend(regular_stories)

    # Determine which stories are newly added
    old_ids = {s['id'] for s in cache.get('stories', [])}
    for story in new_stories:
        story['is_new'] = story['id'] not in old_ids

    new_count = sum(1 for s in new_stories if s.get('is_new'))
    print(f"New stories: {new_count}")

    # Fetch sub-stories for top stories that have URLs and aren't cached
    for story in new_stories:
        if story.get('url') and story['type'] == 'top':
            url = story['url']
            if url not in substories:
                print(f"  Fetching substory: {url}")
                sub = fetch_substory(url)
                if sub:
                    substories[url] = sub
                    print(f"    -> {sub['headline'][:60]}...")
                else:
                    print(f"    -> Failed")
                time.sleep(0.5)  # Be polite

    # Preserve 'presented' state
    presented = set(cache.get('presented', []))

    cache['stories'] = new_stories
    cache['last_update'] = time.time()
    cache['presented'] = list(presented)
    if breaking:
        cache['breaking'] = breaking
    elif 'breaking' in cache:
        del cache['breaking']

    save_cache(cache)
    save_substory_cache(substories)

    print(f"Cache updated. Total stories: {len(new_stories)}, New: {new_count}")
    return cache

def cmd_headlines():
    """Output current headlines as JSON for the DJ. Includes new-story markers."""
    cache = load_cache()
    substories = load_substory_cache()
    stories = cache.get('stories', [])

    if not stories:
        print(json.dumps({"headlines": [], "breaking": None}))
        return

    headlines = []
    for s in stories:
        entry = {
            'headline': s['headline'],
            'type': s['type'],
            'is_new': s.get('is_new', False)
        }
        headlines.append(entry)

    output = {
        'breaking': cache.get('breaking'),
        'headlines': headlines,
        'total': len(headlines),
        'new_count': sum(1 for h in headlines if h['is_new'])
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))

def cmd_next_story():
    """Get the next story that hasn't been presented in depth yet."""
    cache = load_cache()
    substories = load_substory_cache()
    presented = set(cache.get('presented', []))

    # Priority: breaking > top stories > regular stories with text
    for story in cache.get('stories', []):
        sid = story['id']
        if sid in presented:
            continue

        # For top stories, check substory cache for description
        if story['type'] == 'top' and story.get('url'):
            sub = substories.get(story['url'])
            if sub and sub.get('description'):
                result = {
                    'id': sid,
                    'headline': story['headline'],
                    'story': sub['description'],
                    'type': story['type'],
                    'url': story.get('url')
                }
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return

        # For regular stories with inline text
        if story.get('has_story') and story.get('story'):
            result = {
                'id': sid,
                'headline': story['headline'],
                'story': story['story'],
                'type': story['type']
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

    # Nothing left to present
    print(json.dumps({"id": None, "headline": None, "story": None}))

def cmd_mark(story_id):
    """Mark a story as presented in depth."""
    cache = load_cache()
    presented = set(cache.get('presented', []))
    presented.add(story_id)
    cache['presented'] = list(presented)
    save_cache(cache)
    print(f"Marked story {story_id} as presented.")

def cmd_status():
    """Show cache status."""
    cache = load_cache()
    substories = load_substory_cache()
    stories = cache.get('stories', [])
    presented = set(cache.get('presented', []))
    age = time.time() - cache.get('last_update', 0)

    print(f"Cache age: {int(age)}s ({int(age/60)} min)")
    print(f"Stories: {len(stories)}")
    print(f"  Breaking: {'YES' if cache.get('breaking') else 'no'}")
    print(f"  Top: {sum(1 for s in stories if s['type']=='top')}")
    print(f"  Regular: {sum(1 for s in stories if s['type']=='regular')}")
    print(f"  Quicklinks: {sum(1 for s in stories if s['type']=='quicklink')}")
    print(f"  New: {sum(1 for s in stories if s.get('is_new'))}")
    print(f"Presented in depth: {len(presented)}")
    print(f"Cached sub-stories: {len(substories)}")

    # Show unpresented stories with content
    available = []
    for s in stories:
        if s['id'] not in presented and s.get('has_story'):
            available.append(s['headline'][:60])
    print(f"Available for in-depth: {len(available)}")
    for h in available[:5]:
        print(f"  - {h}")

# --- MAIN ---

def main():
    if len(sys.argv) < 2:
        print("Usage: python news_manager.py <command> [args]", file=sys.stderr)
        print("Commands: update, headlines, next_story, mark <id>, status", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == 'update':
        cmd_update()
    elif cmd == 'headlines':
        cmd_headlines()
    elif cmd == 'next_story':
        cmd_next_story()
    elif cmd == 'mark':
        if len(sys.argv) < 3:
            print("Usage: python news_manager.py mark <story_id>", file=sys.stderr)
            sys.exit(1)
        cmd_mark(sys.argv[2])
    elif cmd == 'status':
        cmd_status()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
