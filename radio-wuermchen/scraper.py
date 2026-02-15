# Web Scraper - Template-driven text extraction
#
# Usage: python scraper.py <template_file>
#
# Template format (line-based):
#   URL: <url to fetch>
#   FIELD: <name> | START: <anchor> | END: <anchor>
#   FIELD: <name> | START: <anchor> | END: <anchor>
#   ...
#
# Options (optional lines in template):
#   OUTPUT: <output_file.json>          (default: scrape_result.json)
#   CLEAN: html                         (strip HTML tags, collapse to newlines)
#
# The scraper walks the page text sequentially. After extracting a field,
# the search position advances past the END anchor, so fields are found
# in document order.

import sys
import os
import re
import json
import urllib.request

def parse_template(path):
    """Parse a template file into url, options, and field definitions."""
    url = None
    output = None
    clean = None
    fields = []

    with open(path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue

            if line.upper().startswith('URL:'):
                url = line.split(':', 1)[1].strip()
            elif line.upper().startswith('OUTPUT:'):
                output = line.split(':', 1)[1].strip()
            elif line.upper().startswith('CLEAN:'):
                clean = line.split(':', 1)[1].strip().lower()
            elif line.upper().startswith('FIELD:'):
                # FIELD: name | START: anchor | END: anchor
                parts = line.split('|')
                name = parts[0].split(':', 1)[1].strip()
                start = None
                end = None
                for part in parts[1:]:
                    p = part.strip()
                    if p.upper().startswith('START:'):
                        start = p.split(':', 1)[1].strip()
                    elif p.upper().startswith('END:'):
                        end = p.split(':', 1)[1].strip()
                if name and start and end:
                    fields.append({'name': name, 'start': start, 'end': end})
                else:
                    print(f"WARNING: Incomplete field definition: {line}", file=sys.stderr)

    return url, output, clean, fields


def fetch_url(url):
    """Fetch a URL and return the text content."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        charset = resp.headers.get_content_charset() or 'utf-8'
        return resp.read().decode(charset)


def clean_html(text):
    """Replace sequences of HTML tags with newlines, then clean up."""
    # Replace <br>, <br/>, </p>, </h1>-</h6>, </div>, </li> with newline
    text = re.sub(r'<br\s*/?>',  '\n', text, flags=re.IGNORECASE)
    # Replace block-level closing/opening tags with newline
    text = re.sub(r'</?(h[1-6]|p|div|li|ul|ol|tr|blockquote)\b[^>]*>', '\n', text, flags=re.IGNORECASE)
    # Strip all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode common HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    # Collapse multiple blank lines into one, strip leading/trailing whitespace per line
    lines = [l.strip() for l in text.splitlines()]
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_fields(page_text, fields, do_clean_html):
    """Walk through page_text sequentially, extracting each field."""
    result = {}
    pos = 0

    for field in fields:
        start_idx = page_text.find(field['start'], pos)
        if start_idx == -1:
            print(f"WARNING: START anchor not found for '{field['name']}': {field['start'][:60]}",
                  file=sys.stderr)
            result[field['name']] = None
            continue

        content_start = start_idx + len(field['start'])
        end_idx = page_text.find(field['end'], content_start)
        if end_idx == -1:
            print(f"WARNING: END anchor not found for '{field['name']}': {field['end'][:60]}",
                  file=sys.stderr)
            result[field['name']] = None
            continue

        raw = page_text[content_start:end_idx]
        if do_clean_html:
            raw = clean_html(raw)
        result[field['name']] = raw
        pos = end_idx + len(field['end'])

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <template_file>", file=sys.stderr)
        sys.exit(1)

    template_path = sys.argv[1]
    if not os.path.isabs(template_path):
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), template_path)

    url, output_file, clean_mode, fields = parse_template(template_path)

    if not url:
        print("ERROR: No URL found in template.", file=sys.stderr)
        sys.exit(1)
    if not fields:
        print("ERROR: No FIELD definitions found in template.", file=sys.stderr)
        sys.exit(1)

    # Default output path: same directory as template
    if not output_file:
        output_file = "scrape_result.json"
    if not os.path.isabs(output_file):
        output_file = os.path.join(os.path.dirname(template_path), output_file)

    print(f"Fetching: {url}")
    page_text = fetch_url(url)
    print(f"Fetched {len(page_text)} chars")

    do_clean = (clean_mode == 'html')
    result = extract_fields(page_text, fields, do_clean)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Output written to: {output_file}")
    for name, val in result.items():
        preview = (val[:80] + '...') if val and len(val) > 80 else val
        print(f"  {name}: {preview}")


if __name__ == "__main__":
    main()
