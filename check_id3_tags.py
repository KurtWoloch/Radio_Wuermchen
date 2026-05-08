import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pyodbc
import json
import os

base = r'C:\Users\kurt_\Musikprogramm'

# Get a sample of file paths from the database
conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={base}\\rw_Files2000.mdb;'
conn = pyodbc.connect(conn_str)
cur = conn.cursor()
cur.execute('SELECT TOP 100 Titel_Nr, URL, Titel FROM Tab_Files WHERE URL IS NOT NULL')
files = cur.fetchall()
conn.close()

# Try to read ID3 tags
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3
    has_mutagen = True
except ImportError:
    has_mutagen = False
    print('mutagen not installed, trying mutagenx...')

if not has_mutagen:
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3
        has_mutagen = True
    except ImportError:
        print('Neither mutagen nor mutagenx available.')

if has_mutagen:
    # Check which ID3 tags are present
    tag_stats = {}
    year_count = 0
    genre_count = 0
    bpm_count = 0
    language_count = 0
    mood_count = 0
    total = 0
    errors = 0
    
    sample_years = []
    sample_genres = []
    sample_bpm = []
    
    for row in files:
        filepath = row[1]
        if not filepath or not os.path.exists(filepath):
            continue
        try:
            audio = MP3(filepath)
            if audio.tags:
                total += 1
                for key in audio.tags.keys():
                    tag_stats[key] = tag_stats.get(key, 0) + 1
                
                # Check specific fields
                # Year: TDRC or TYER
                year = None
                for year_key in ['TDRC', 'TYER', 'TORY']:
                    if year_key in audio.tags:
                        year = str(audio.tags[year_key])
                        break
                if year:
                    year_count += 1
                    if len(sample_years) < 10:
                        sample_years.append(year)
                
                # Genre: TCON
                if 'TCON' in audio.tags:
                    genre_count += 1
                    if len(sample_genres) < 10:
                        sample_genres.append(str(audio.tags['TCON']))
                
                # BPM: TBPM
                if 'TBPM' in audio.tags:
                    bpm_count += 1
                    if len(sample_bpm) < 10:
                        sample_bpm.append(str(audio.tags['TBPM']))
                
                # Language: TLAN
                if 'TLAN' in audio.tags:
                    language_count += 1
                
                # Mood: TMOO or COMM
                if 'TMOO' in audio.tags:
                    mood_count += 1
        except Exception as e:
            errors += 1
    
    print(f'Checked {total} files ({errors} errors)')
    print(f'\nField coverage:')
    print(f'  Year (TDRC/TYER): {year_count} ({100*year_count/total:.1f}%)')
    print(f'  Genre (TCON): {genre_count} ({100*genre_count/total:.1f}%)')
    print(f'  BPM (TBPM): {bpm_count} ({100*bpm_count/total:.1f}%)')
    print(f'  Language (TLAN): {language_count} ({100*language_count/total:.1f}%)')
    print(f'  Mood (TMOO): {mood_count} ({100*mood_count/total:.1f}%)')
    
    print(f'\nSample years: {sample_years}')
    print(f'Sample genres: {sample_genres}')
    print(f'Sample BPM: {sample_bpm}')
    
    print(f'\nTop ID3 tags:')
    for key, count in sorted(tag_stats.items(), key=lambda x: -x[1])[:20]:
        print(f'  {key}: {count}')
else:
    print('Cannot read ID3 tags - no library available')
