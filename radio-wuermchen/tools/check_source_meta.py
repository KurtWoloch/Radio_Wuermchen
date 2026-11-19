import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

d = json.load(open(r'C:\Users\kurt_\.openclaw\wiki\main\.openclaw-wiki\cache\agent-digest.json', encoding='utf-8'))
src = [p for p in d['pages'] if p.get('kind') == 'source']
best = [p for p in src if p.get('bestUsedFor')]
not_enough = [p for p in src if p.get('notEnoughFor')]

print(f'bestUsedFor non-empty: {len(best)}')
if best:
    for p in best[:3]:
        print(f'  {p["path"]}: {p["bestUsedFor"]}')

print(f'notEnoughFor non-empty: {len(not_enough)}')
if not_enough:
    for p in not_enough[:3]:
        print(f'  {p["path"]}: {p["notEnoughFor"]}')

print()
freshness = {}
for p in src:
    fl = p.get('freshnessLevel', 'none')
    freshness[fl] = freshness.get(fl, 0) + 1
print('Freshness levels:', freshness)

recent = sorted([p for p in src if p.get('lastTouchedAt')], key=lambda p: p['lastTouchedAt'], reverse=True)
print(f'Sources with lastTouchedAt: {len(recent)}')
print('Most recent touches:')
for p in recent[:8]:
    path_short = p['path'].split('/')[-1][:70] if '/' in p['path'] else p['path'][:70]
    print(f'  {p["lastTouchedAt"]}  {path_short}')
