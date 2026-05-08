import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

path = r'C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\dj_history.json'
with open(path, 'r', encoding='utf-8') as f:
    history = json.load(f)

fixed = []
for entry in history:
    t = entry.get('track', '')
    if isinstance(t, dict):
        entry['track'] = f"{t.get('artist', '?')} - {t.get('title', '?')}"
    fixed.append(entry)

with open(path, 'w', encoding='utf-8') as f:
    json.dump(fixed, f, indent=2, ensure_ascii=False)

print(f'Fixed {len(fixed)} entries')
