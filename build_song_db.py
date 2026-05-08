import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pyodbc
import json
import os
import signal
from collections import Counter, defaultdict

base = r'C:\Users\kurt_\Musikprogramm'

def connect(db):
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={base}\\{db};'
    return pyodbc.connect(conn_str)

# === 1. Tab_Files: Titel_Nr → URL ===
print('Reading Tab_Files...', flush=True)
conn = connect('rw_Files2000.mdb')
cur = conn.cursor()
cur.execute('SELECT Titel_Nr, URL, Titel FROM Tab_Files')
files = {}
for row in cur.fetchall():
    files[row[0]] = {'url': row[1], 'file_title': row[2]}
conn.close()
print(f'  {len(files)} files', flush=True)

# === 2. Tab_Titel + Tab_Interpreten ===
print('Reading Tab_Titel + Tab_Interpreten...', flush=True)
conn = connect('Tontraeger.mdb')
cur = conn.cursor()
cur.execute('SELECT Interpret_Nr, Interpret, Suchbegriff FROM Tab_Interpreten')
artists = {}
for row in cur.fetchall():
    # Use Suchbegriff (full name) instead of Interpret (sortable name)
    artists[row[0]] = row[2] if row[2] else row[1]
cur.execute('SELECT Titel_Nr, Titel, VorTitel, Interpret_Nr, Herstellungsdatum, Suchbegriff FROM Tab_Titel')
titles = {}
for row in cur.fetchall():
    # Combine VorTitel + Titel for full title
    volltitel = ((row[2] or '') + ' ' + (row[1] or '')).strip()
    titles[row[0]] = {
        'title': volltitel if volltitel else row[1],
        'interpret_nr': row[3],
        'artist': artists.get(row[3], '?'),
        'herstellungsdatum': row[4],
        'suchbegriff': row[5],
    }
conn.close()
print(f'  {len(titles)} titles, {len(artists)} artists', flush=True)

# === 3. Tab_Aehnlich ===
print('Reading Tab_Aehnlich...', flush=True)
conn = connect('rw_Aehnlichkeiten.mdb')
cur = conn.cursor()
cur.execute('SELECT Titelnr, Kategorien, Bekanntheitsgrad_K, Status_oeffentlich, Bedeutung_K FROM Tab_Aehnlich')
aehnlich = {}
for row in cur.fetchall():
    aehnlich[row[0]] = {
        'kategorien': row[1],
        'bekanntheit': row[2],
        'status': row[3],
        'bedeutung': row[4],
    }
conn.close()
print(f'  {len(aehnlich)} entries', flush=True)

# === 3b. Read ID3 tags (with progress and timeout) ===
print('Reading ID3 tags from MP3 files...', flush=True)
from mutagen.mp3 import MP3
import threading

id3_data = {}
id3_errors = 0
id3_year_count = 0
id3_genre_count = 0
id3_bpm_count = 0
processed = 0
skipped = 0

def read_id3_with_timeout(filepath, timeout=5):
    """Read ID3 tags with a timeout."""
    result = [None]
    def target():
        try:
            audio = MP3(filepath)
            if audio.tags:
                entry = {}
                for year_key in ['TDRC', 'TYER', 'TORY']:
                    if year_key in audio.tags:
                        year_str = str(audio.tags[year_key]).strip()
                        try:
                            entry['id3_year'] = int(year_str[:4])
                            break
                        except:
                            pass
                if 'TCON' in audio.tags:
                    entry['id3_genre'] = str(audio.tags['TCON']).strip()
                if 'TBPM' in audio.tags:
                    try:
                        entry['id3_bpm'] = float(str(audio.tags['TBPM']).strip())
                    except:
                        pass
                if 'TLAN' in audio.tags:
                    entry['id3_language'] = str(audio.tags['TLAN']).strip()
                result[0] = entry
        except:
            pass
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    return result[0]

for titel_nr, file_info in files.items():
    filepath = file_info.get('url')
    if not filepath or not os.path.exists(filepath):
        skipped += 1
        continue
    
    entry = read_id3_with_timeout(filepath, timeout=3)
    processed += 1
    
    if entry:
        id3_data[titel_nr] = entry
        if 'id3_year' in entry:
            id3_year_count += 1
        if 'id3_genre' in entry:
            id3_genre_count += 1
        if 'id3_bpm' in entry:
            id3_bpm_count += 1
    
    if processed % 1000 == 0:
        print(f'  {processed} processed, {len(id3_data)} with data, {skipped} skipped...', flush=True)

print(f'  Done: {processed} processed, {skipped} skipped, {len(id3_data)} with ID3 data', flush=True)
print(f'  Years: {id3_year_count}, Genres: {id3_genre_count}, BPM: {id3_bpm_count}', flush=True)

# === 4. Tab_Scan: Radio Würmchen KI ===
print('Reading Radio Würmchen KI scans...', flush=True)
conn = connect('rw_Aehnlichkeiten.mdb')
cur = conn.cursor()
cur.execute('SELECT Titelnr, Zeit FROM Tab_Scan WHERE Sender = -264 ORDER BY Zeit')
rw_scans = []
for row in cur.fetchall():
    rw_scans.append({'titelnr': row[0], 'zeit': row[1].isoformat() if row[1] else None})
conn.close()
print(f'  {len(rw_scans)} scans', flush=True)

rw_play_count = Counter()
rw_last_played = {}
for scan in rw_scans:
    tn = scan['titelnr']
    rw_play_count[tn] += 1
    if scan['zeit'] and (tn not in rw_last_played or scan['zeit'] > rw_last_played[tn]):
        rw_last_played[tn] = scan['zeit']

# === 5. Kurt's ratings ===
print('Reading Kurt ratings...', flush=True)
conn = connect('rw_bewertung2000.mdb')
cur = conn.cursor()
cur.execute('SELECT Titel_Nr, Wertung, letztes_Datum FROM Tab_Wertung_pro_Person WHERE Person_Nr = 95')
kurt_ratings = {}
for row in cur.fetchall():
    kurt_ratings[row[0]] = {'wertung': row[1], 'letztes_datum': row[2].isoformat() if row[2] else None}
conn.close()
print(f'  {len(kurt_ratings)} ratings', flush=True)

# === 6. Show ratings ===
print('Reading show ratings...', flush=True)
conn = connect('rw_bewertung2000.mdb')
cur = conn.cursor()
cur.execute('SELECT Person_Nr, Titel_Nr, Wertung FROM Tab_Wertung_pro_Person WHERE Person_Nr BETWEEN 1440 AND 1454')
show_ratings = defaultdict(dict)
for row in cur.fetchall():
    show_ratings[row[1]][row[0]] = row[2]
conn.close()
print(f'  {len(show_ratings)} titles with show ratings', flush=True)

# === 7. Parse Kategorien ===
def parse_kategorien(kat_str):
    if not kat_str:
        return {}
    tags = [t.strip() for t in kat_str.split(',')]
    result = {'genre_tags': [], 'tempo_tags': [], 'mood_tags': [], 'instrument_tags': [], 'voice_tags': [], 'other_tags': []}
    
    genre_kw = {'pop', 'rock', 'schlager', 'oldie', 'country', 'jazz', 'blues', 'r&b', 'reggae', 'dance',
                'disco', 'soul', 'funk', 'metal', 'punk', 'folk', 'classical', 'klassik', 'electro',
                'hip-hop', 'rap', 'gospel', 'latin', 'ska', 'grunge', 'alternative', "rock'n'roll",
                'indie', 'ambient', 'new wave', 'synthie', 'beat', 'chanson', 'musical', 'volksmusik',
                'polka', 'swing', 'bebop', 'bossa nova', 'tango', 'walzer'}
    tempo_kw = {'ballade', 'langsam', 'schnell', 'mittel', '6/8', 'shuffle', '16', '3/4', '4/4', 'walzer', 'temporell', 'getragen'}
    mood_kw = {'schön gesungen', 'schmutzig', 'bombastisch', 'rauh', 'melancholisch', 'fröhlich', 'traurig',
               'energisch', 'ruhig', 'aggressiv', 'romantisch', 'episch', 'dramatisch', 'verspielt', 'düster',
               'heiter', 'nostalgisch', 'sehnsüchtig', 'verträumt', 'melodramatisch'}
    instr_kw = {'klavier', 'orgel', 'gitarre', 'streicher', 'akustisch', 'synthesizer', 'brass', 'bläsersatz',
                'saxophon', 'geige', 'cello', 'flöte', 'harmonika', 'akkordeon', 'banjo', 'mundharmonika', 'schlagzeug', 'bass'}
    voice_kw = {'weiblich', 'männlich', 'chorgesang', 'duett', 'hoch', 'tief', 'rauh', 'sanft', 'kraftvoll'}
    
    for tag in tags:
        tl = tag.lower().strip()
        if tl in genre_kw: result['genre_tags'].append(tag)
        elif tl in tempo_kw: result['tempo_tags'].append(tag)
        elif tl in mood_kw: result['mood_tags'].append(tag)
        elif tl in instr_kw: result['instrument_tags'].append(tag)
        elif tl in voice_kw: result['voice_tags'].append(tag)
        else: result['other_tags'].append(tag)
    return result

# === 8. Build Song Database ===
print('\nBuilding song database...', flush=True)
songs = []
merged_year_count = 0

for titel_nr, file_info in files.items():
    title_info = titles.get(titel_nr, {})
    aeh_info = aehnlich.get(titel_nr, {})
    id3 = id3_data.get(titel_nr, {})
    kat = parse_kategorien(aeh_info.get('kategorien', ''))
    
    herst = title_info.get('herstellungsdatum', '')
    id3_year = id3.get('id3_year')
    
    year = None
    year_source = None
    if id3_year:
        year = id3_year
        year_source = 'id3'
        merged_year_count += 1
    elif herst:
        try:
            year = int(herst[:4])
            year_source = 'herstellungsdatum'
        except:
            year_source = 'herstellungsdatum_raw'
    
    decade = None
    if year:
        decade = f"{(year // 10) * 10}s"
    elif herst:
        decade = herst
    
    id3_genre = id3.get('id3_genre')
    all_genres = list(kat.get('genre_tags', []))
    if id3_genre and id3_genre not in all_genres and id3_genre != 'Other':
        all_genres.insert(0, id3_genre)
    
    language = None
    raw_kat = aeh_info.get('kategorien', '')
    if raw_kat:
        kl = raw_kat.lower()
        if 'deutsch' in kl: language = 'de'
        elif 'französisch' in kl: language = 'fr'
        elif 'spanisch' in kl: language = 'es'
        elif 'italienisch' in kl: language = 'it'
        elif 'schwedisch' in kl: language = 'sv'
        elif 'japanisch' in kl: language = 'ja'
        elif 'instrumental' in kl: language = 'instrumental'
        else: language = 'en'
    
    song = {
        'titel_nr': titel_nr,
        'filename': file_info.get('url', '').split('\\')[-1] if file_info.get('url') else None,
        'filepath': file_info.get('url'),
        'artist': title_info.get('artist', '?'),
        'title': title_info.get('title', '?'),
        'year': year, 'year_source': year_source, 'decade': decade,
        'herstellungsdatum': herst or None, 'language': language,
        'genre_tags': all_genres, 'tempo_tags': kat.get('tempo_tags', []),
        'mood_tags': kat.get('mood_tags', []), 'instrument_tags': kat.get('instrument_tags', []),
        'voice_tags': kat.get('voice_tags', []), 'other_tags': kat.get('other_tags', []),
        'raw_kategorien': aeh_info.get('kategorien'),
        'id3_genre': id3_genre, 'id3_bpm': id3.get('id3_bpm'), 'id3_language': id3.get('id3_language'),
        'bekanntheit': aeh_info.get('bekanntheit'), 'status_oeffentlich': aeh_info.get('status'),
        'bedeutung': aeh_info.get('bedeutung'),
        'rw_play_count': rw_play_count.get(titel_nr, 0), 'rw_last_played': rw_last_played.get(titel_nr),
        'kurt_rating': kurt_ratings.get(titel_nr, {}).get('wertung'),
        'kurt_rating_date': kurt_ratings.get(titel_nr, {}).get('letztes_datum'),
        'show_ratings': {str(k): v for k, v in show_ratings.get(titel_nr, {}).items()},
        'energy': None, 'mood': None, 'tempo_bpm': None, 'show_fit': None,
    }
    songs.append(song)

print(f'  {len(songs)} songs, {merged_year_count} ID3 years merged', flush=True)

# === 9. Export ===
output_path = r'C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\song-database-v1.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(songs, f, ensure_ascii=False, indent=2)
print(f'\nExported to {output_path}', flush=True)

# === 10. Stats ===
with_genre = sum(1 for s in songs if s['genre_tags'])
with_tempo = sum(1 for s in songs if s['tempo_tags'])
with_mood = sum(1 for s in songs if s['mood_tags'])
with_rw = sum(1 for s in songs if s['rw_play_count'] > 0)
with_rating = sum(1 for s in songs if s['kurt_rating'] is not None)
with_decade = sum(1 for s in songs if s['decade'])
with_year = sum(1 for s in songs if s['year'])
with_year_id3 = sum(1 for s in songs if s.get('year_source') == 'id3')
with_year_herst = sum(1 for s in songs if s.get('year_source') == 'herstellungsdatum')
with_language = sum(1 for s in songs if s['language'])

print(f'\nStats:')
print(f'  With genre tags: {with_genre} ({100*with_genre/len(songs):.1f}%)')
print(f'  With tempo tags: {with_tempo} ({100*with_tempo/len(songs):.1f}%)')
print(f'  With mood tags: {with_mood} ({100*with_mood/len(songs):.1f}%)')
print(f'  With year (any): {with_year} ({100*with_year/len(songs):.1f}%)')
print(f'    From ID3: {with_year_id3} ({100*with_year_id3/len(songs):.1f}%)')
print(f'    From Herstellungsdatum: {with_year_herst} ({100*with_year_herst/len(songs):.1f}%)')
print(f'  With decade: {with_decade} ({100*with_decade/len(songs):.1f}%)')
print(f'  With language: {with_language} ({100*with_language/len(songs):.1f}%)')
print(f'  With RW play count: {with_rw} ({100*with_rw/len(songs):.1f}%)')
print(f'  With Kurt rating: {with_rating} ({100*with_rating/len(songs):.1f}%)')

bek_vals = []
for s in songs:
    if s['bekanntheit']:
        try:
            bek_vals.append(float(s['bekanntheit'].replace(',', '.')))
        except:
            pass
print(f'  With Bekanntheit: {len(bek_vals)} ({100*len(bek_vals)/len(songs):.1f}%)')
if bek_vals:
    print(f'    Avg: {sum(bek_vals)/len(bek_vals):.2f}, Min: {min(bek_vals):.1f}, Max: {max(bek_vals):.1f}')

status_vals = [s['status_oeffentlich'] for s in songs if s['status_oeffentlich']]
print(f'  With Status_oeffentlich: {len(status_vals)} ({100*len(status_vals)/len(songs):.1f}%)')
