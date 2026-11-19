import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pyodbc
import json

base = r'C:\Users\kurt_\Musikprogramm'

def connect(db):
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={base}\\{db};'
    return pyodbc.connect(conn_str)

# Read corrected artist names (Suchbegriff instead of Interpret)
print('Reading Tab_Interpreten (corrected)...', flush=True)
conn = connect('Tontraeger.mdb')
cur = conn.cursor()
cur.execute('SELECT Interpret_Nr, Interpret, Suchbegriff FROM Tab_Interpreten')
artists = {}
for row in cur.fetchall():
    artists[row[0]] = row[2] if row[2] else row[1]
conn.close()
print(f'  {len(artists)} artists', flush=True)

# Read corrected titles (VorTitel + Titel)
print('Reading Tab_Titel (corrected)...', flush=True)
conn = connect('Tontraeger.mdb')
cur = conn.cursor()
cur.execute('SELECT Titel_Nr, Titel, VorTitel, Interpret_Nr FROM Tab_Titel')
titles = {}
for row in cur.fetchall():
    volltitel = ((row[2] or '') + ' ' + (row[1] or '')).strip()
    titles[row[0]] = {
        'title': volltitel if volltitel else row[1],
        'interpret_nr': row[3],
        'artist': artists.get(row[3], '?'),
    }
conn.close()
print(f'  {len(titles)} titles', flush=True)

# Load classified database
print('Loading classified database...', flush=True)
DB_PATH = r'C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\song-database-v1-classified.json'
with open(DB_PATH, 'r', encoding='utf-8') as f:
    songs = json.load(f)
print(f'  {len(songs)} songs', flush=True)

# Update artist and title
updated = 0
for song in songs:
    tn = song['titel_nr']
    if tn in titles:
        new_artist = titles[tn]['artist']
        new_title = titles[tn]['title']
        
        if song['artist'] != new_artist or song['title'] != new_title:
            song['artist'] = new_artist
            song['title'] = new_title
            updated += 1

print(f'  Updated {updated} songs', flush=True)

# Save
with open(DB_PATH, 'w', encoding='utf-8') as f:
    json.dump(songs, f, ensure_ascii=False, indent=2)
print(f'Saved to {DB_PATH}', flush=True)

# Also update the V1 copy
import shutil
shutil.copy2(DB_PATH, r'C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\song-database-v1.json')
print('Copied to song-database-v1.json', flush=True)

# Show some examples of corrected names
print('\nSample corrections:', flush=True)
examples = [
    s for s in songs 
    if s['artist'] != '?' and len(s['artist']) > 15
][:10]
for s in examples:
    print(f"  {s['artist']} - {s['title']}")
