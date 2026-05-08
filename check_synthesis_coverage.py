import sys, io, json, re, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

wiki_dir = r'C:\Users\kurt_\.openclaw\wiki\main'

# Gather all source file IDs
digest = json.load(open(os.path.join(wiki_dir, '.openclaw-wiki', 'cache', 'agent-digest.json'), encoding='utf-8'))

source_ids = set()
source_paths = {}
for page in digest.get('pages', []):
    if page.get('kind') == 'source':
        sid = page['id']
        source_ids.add(sid)
        source_paths[sid] = page.get('path', '?')

# Gather all sourceIds referenced in syntheses
synth_dir = os.path.join(wiki_dir, 'syntheses')
referenced = set()
synth_sources = {}  # synthesis path -> list of source ids
for fn in os.listdir(synth_dir):
    if fn == 'index.md' or not fn.endswith('.md'):
        continue
    fpath = os.path.join(synth_dir, fn)
    content = open(fpath, encoding='utf-8').read()
    # Extract sourceIds from YAML frontmatter: sourceIds:\n  - name\n  - name
    m = re.search(r'^sourceIds:\s*\n((?:\s*-\s*\S+\n?)+)', content, re.MULTILINE)
    if m:
        ids = re.findall(r'^\s*-\s*(\S+)', m.group(1), re.MULTILINE)
        # sourceIds in synthesis are short form, in digest they're full 'source.bridge.workspace-d9997e04.memory-YYYY-MM-DD-hash'
        # Match by suffix (the hash/date part)
        for sid in ids:
            referenced.add(sid)
        synth_sources[fpath] = ids

# Matching: short synthesis IDs (e.g. 'bridge-workspace-d9997e04-memory-2026-04-21-dc4e9378')
# match full digest IDs (e.g. 'source.bridge.workspace-d9997e04.memory-2026-04-21-dc4e9378')
# Strategy: build a lookup by the unique suffix after the common prefix
matched_source_ids = set()
for full_id in source_ids:
    # Convert dots to hyphens, remove 'source.' prefix
    short_form = full_id.replace('source.', '').replace('.', '-')
    if short_form in referenced or full_id in referenced:
        matched_source_ids.add(full_id)

# Also try matching by just the last segment (hash part)
# Full: source.bridge.workspace-d9997e04.memory-2026-04-21-dc4e9378
# Short: bridge-workspace-d9997e04-memory-2026-04-21-dc4e9378
# The actual match: workspace part is the same, just separated by hyphen vs dot
for full_id in source_ids:
    for short_id in referenced:
        if full_id.endswith(short_id) or short_id.endswith(full_id.split('.')[-1]):
            matched_source_ids.add(full_id)
            break
        # Try converting: source.X.Y.Z -> X-Y-Z
        candidate = full_id.replace('source.', '').replace('.', '-')
        if candidate == short_id:
            matched_source_ids.add(full_id)
            break

unreferenced = source_ids - matched_source_ids

print(f"Total source pages: {len(source_ids)}")
print(f"Total syntheses: {len(synth_sources)}")
print(f"Referenced sources: {len(matched_source_ids)}")
print(f"Unreferenced sources: {len(unreferenced)}")
print(f"Coverage: {len(matched_source_ids)}/{len(source_ids)} = {100*len(matched_source_ids)/len(source_ids):.1f}%")
print()

if unreferenced:
    print("UNREFERENCED SOURCES (first 40):")
    count = 0
    for sid in sorted(unreferenced):
        if count >= 40:
            remaining = len(unreferenced) - 40
            print(f"  ... and {remaining} more")
            break
        p = source_paths.get(sid, '?')
        # Extract date from filename if possible
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', p)
        date_str = date_match.group(1) if date_match else '???'
        print(f"  {date_str}  {p}")
        count += 1
