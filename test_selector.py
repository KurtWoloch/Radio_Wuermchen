import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add the radio-wuermchen directory to the path
rw_dir = r'C:\Users\kurt_\.openclaw\workspace\radio-wuermchen'
sys.path.insert(0, rw_dir)

from song_selector import SongSelector

selector = SongSelector()

print('=== Test: Pop, Energy 5 ===')
results = selector.select(energy_target=5, genre_prefer=['Pop'], count=5)
for r in results:
    print(f"  {r['artist']} - {r['title']} (energy={r['energy']}, score={r['score']})")

print()
print('=== Test: Rock, Energy 7 ===')
results = selector.select(energy_target=7, genre_prefer=['Rock'], count=5)
for r in results:
    print(f"  {r['artist']} - {r['title']} (energy={r['energy']}, score={r['score']})")

print()
print('=== Test: Calm, Energy 3 ===')
results = selector.select(energy_target=3, count=5)
for r in results:
    print(f"  {r['artist']} - {r['title']} (energy={r['energy']}, score={r['score']})")
