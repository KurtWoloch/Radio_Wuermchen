import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json

DB_PATH = r'C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\song-database-v1.json'

print('Loading song database...', flush=True)
with open(DB_PATH, 'r', encoding='utf-8') as f:
    songs = json.load(f)
print(f'  {len(songs)} songs loaded', flush=True)

# === Rule-based energy classification ===
# Energy scale: 1 (very calm) to 10 (very energetic)

# Genre → base energy
genre_energy = {
    'ballade': 2, 'chanson': 3, 'jazz': 4, 'folk': 4, 'klassik': 3, 'classical': 3,
    'bossa nova': 3, 'tango': 5, 'walzer': 4, 'polka': 5, 'swing': 5,
    'pop': 5, 'beat': 6, 'rock': 7, 'indie': 6, 'alternative': 6,
    'country': 5, 'blues': 4, 'soul': 5, 'r&b': 5, 'gospel': 5,
    'reggae': 5, 'ska': 7, 'punk': 8, 'metal': 9, 'grunge': 8,
    'hip-hop': 6, 'rap': 6, 'dance': 7, 'disco': 7, 'electro': 7,
    'funk': 7, 'synthie': 6, 'new wave': 6, 'ambient': 2,
    'schlager': 5, 'volksmusik': 4, 'oldie': 5, 'musical': 5,
}

# Tempo tags → energy modifier
tempo_energy = {
    'ballade': -2, 'langsam': -2, 'getragen': -1, 'mittel': 0,
    'schnell': 2, 'temporell': 1, '6/8': 0, 'shuffle': 1, '16': 1,
    '3/4': -1, '4/4': 0, 'walzer': -1,
}

# Mood tags → energy modifier
mood_energy = {
    'ruhig': -2, 'melancholisch': -1, 'verträumt': -1, 'melodramatisch': -1,
    'traurig': -1, 'sehnsüchtig': -1, 'nostalgisch': -1,
    'schön gesungen': 0, 'sanft': -1, 'romantisch': -1,
    'heiter': 1, 'fröhlich': 1, 'verspielt': 1, 'episch': 1,
    'dramatisch': 1, 'energisch': 2, 'kraftvoll': 2, 'bombastisch': 2,
    'aggressiv': 3, 'schmutzig': 1, 'rauh': 1, 'düster': -1,
}

def classify_energy(song):
    """Estimate energy from available tags."""
    scores = []
    
    # From genre tags
    for tag in song.get('genre_tags', []):
        tag_lower = tag.lower().strip()
        if tag_lower in genre_energy:
            scores.append(genre_energy[tag_lower])
    
    # From tempo tags
    for tag in song.get('tempo_tags', []):
        tag_lower = tag.lower().strip()
        if tag_lower in tempo_energy:
            scores.append(tempo_energy[tag_lower] + 5)  # normalize to 1-10
    
    # From mood tags
    for tag in song.get('mood_tags', []):
        tag_lower = tag.lower().strip()
        if tag_lower in mood_energy:
            scores.append(mood_energy[tag_lower] + 5)  # normalize to 1-10
    
    if not scores:
        return None
    
    # Average and clamp to 1-10
    avg = sum(scores) / len(scores)
    return max(1, min(10, round(avg)))

def classify_mood(song):
    """Estimate mood from available tags."""
    mood_tags = song.get('mood_tags', [])
    if not mood_tags:
        # Try to infer from genre
        genre = [g.lower() for g in song.get('genre_tags', [])]
        if any(g in genre for g in ['ballade', 'chanson']):
            return 'melancholisch'
        if any(g in genre for g in ['punk', 'metal', 'grunge']):
            return 'aggressiv'
        if any(g in genre for g in ['dance', 'disco', 'funk']):
            return 'energisch'
        if any(g in genre for g in ['jazz', 'bossa nova']):
            return 'entspannt'
        return None
    
    # Return the first mood tag as primary mood
    return mood_tags[0].lower()

def classify_tempo_bpm(song):
    """Estimate BPM from tempo tags."""
    tempo_tags = [t.lower() for t in song.get('tempo_tags', [])]
    
    if 'ballade' in tempo_tags or 'langsam' in tempo_tags:
        return 70
    if 'getragen' in tempo_tags:
        return 85
    if 'mittel' in tempo_tags:
        return 110
    if 'temporell' in tempo_tags:
        return 125
    if 'schnell' in tempo_tags:
        return 140
    if '6/8' in tempo_tags:
        return 130
    if 'shuffle' in tempo_tags:
        return 100
    if '16' in tempo_tags:
        return 120
    
    # From genre
    genre = [g.lower() for g in song.get('genre_tags', [])]
    if any(g in genre for g in ['ballade', 'chanson']):
        return 70
    if any(g in genre for g in ['hip-hop', 'rap']):
        return 90
    if any(g in genre for g in ['rock', 'beat']):
        return 120
    if any(g in genre for g in ['dance', 'disco', 'electro']):
        return 128
    if any(g in genre for g in ['metal', 'punk', 'grunge']):
        return 150
    if any(g in genre for g in ['jazz', 'swing']):
        return 110
    if any(g in genre for g in ['country', 'folk']):
        return 100
    if any(g in genre for g in ['reggae', 'ska']):
        return 90
    
    return None

# Apply rule-based classification
classified_energy = 0
classified_mood = 0
classified_tempo = 0

for song in songs:
    # Energy
    if song.get('energy') is None:
        e = classify_energy(song)
        if e is not None:
            song['energy'] = e
            song['energy_source'] = 'rule'
            classified_energy += 1
    
    # Mood
    if song.get('mood') is None:
        m = classify_mood(song)
        if m is not None:
            song['mood'] = m
            song['mood_source'] = 'rule'
            classified_mood += 1
    
    # Tempo BPM
    if song.get('tempo_bpm') is None:
        t = classify_tempo_bpm(song)
        if t is not None:
            song['tempo_bpm'] = t
            song['tempo_bpm_source'] = 'rule'
            classified_tempo += 1

print(f'\nRule-based classification results:')
print(f'  Energy: {classified_energy} classified ({100*classified_energy/len(songs):.1f}%)')
print(f'  Mood: {classified_mood} classified ({100*classified_mood/len(songs):.1f}%)')
print(f'  Tempo BPM: {classified_tempo} classified ({100*classified_tempo/len(songs):.1f}%)')

# Count remaining gaps
still_needs_energy = sum(1 for s in songs if s.get('energy') is None)
still_needs_mood = sum(1 for s in songs if s.get('mood') is None)
still_needs_tempo = sum(1 for s in songs if s.get('tempo_bpm') is None)

print(f'\nRemaining gaps:')
print(f'  Energy: {still_needs_energy}')
print(f'  Mood: {still_needs_mood}')
print(f'  Tempo BPM: {still_needs_tempo}')

# Save updated database
output_path = r'C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\song-database-v1-classified.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(songs, f, ensure_ascii=False, indent=2)
print(f'\nDatabase updated and saved to {output_path}')

# Stats
energy_vals = [s['energy'] for s in songs if s.get('energy') is not None]
if energy_vals:
    print(f'\nEnergy distribution:')
    from collections import Counter
    dist = Counter(energy_vals)
    for e in sorted(dist.keys()):
        print(f'  {e}: {dist[e]} songs ({100*dist[e]/len(energy_vals):.1f}%)')
