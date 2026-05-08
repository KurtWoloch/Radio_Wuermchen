import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import os

DB_PATH = r'C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\song-database-v1.json'

# Load database
print('Loading song database...', flush=True)
with open(DB_PATH, 'r', encoding='utf-8') as f:
    songs = json.load(f)

print(f'  {len(songs)} songs loaded', flush=True)

# Find songs that need classification
needs_energy = [s for s in songs if s.get('energy') is None]
needs_mood = [s for s in songs if s.get('mood') is None]
needs_tempo = [s for s in songs if s.get('tempo_bpm') is None]

print(f'\nNeeds classification:')
print(f'  Energy: {len(needs_energy)}')
print(f'  Mood: {len(needs_mood)}')
print(f'  Tempo BPM: {len(needs_tempo)}')

# Prepare batches for LLM classification
# Each batch: 20 songs with their metadata
BATCH_SIZE = 20

def prepare_batch(batch_songs):
    """Prepare a batch of songs for LLM classification."""
    lines = []
    for i, s in enumerate(batch_songs):
        parts = [f"{i+1}. \"{s.get('title', '?')}\" by {s.get('artist', '?')}"]
        if s.get('genre_tags'):
            parts.append(f"   Genre: {', '.join(s['genre_tags'])}")
        if s.get('tempo_tags'):
            parts.append(f"   Tempo: {', '.join(s['tempo_tags'])}")
        if s.get('mood_tags'):
            parts.append(f"   Mood: {', '.join(s['mood_tags'])}")
        if s.get('voice_tags'):
            parts.append(f"   Voice: {', '.join(s['voice_tags'])}")
        if s.get('instrument_tags'):
            parts.append(f"   Instruments: {', '.join(s['instrument_tags'])}")
        if s.get('decade'):
            parts.append(f"   Decade: {s['decade']}")
        if s.get('language'):
            parts.append(f"   Language: {s['language']}")
        lines.append('\n'.join(parts))
    return '\n\n'.join(lines)

def parse_llm_response(response_text, batch_size):
    """Parse LLM response to extract energy and mood for each song."""
    results = []
    lines = response_text.strip().split('\n')
    
    current_idx = None
    current_energy = None
    current_mood = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Look for patterns like "1. energy: 7, mood: upbeat" or "Song 1: energy=7, mood=upbeat"
        import re
        
        # Try to match numbered entries
        match = re.match(r'^(\d+)[\.\):]\s*(.*)', line)
        if match:
            # Save previous entry
            if current_idx is not None:
                results.append({'energy': current_energy, 'mood': current_mood})
            
            current_idx = int(match.group(1))
            rest = match.group(2)
            
            # Parse energy and mood from the rest
            energy_match = re.search(r'energy\s*[=:]\s*(\d+)', rest, re.IGNORECASE)
            mood_match = re.search(r'mood\s*[=:]\s*([^,\n]+)', rest, re.IGNORECASE)
            
            current_energy = int(energy_match.group(1)) if energy_match else None
            current_mood = mood_match.group(1).strip() if mood_match else None
        else:
            # Try to parse energy/mood from continuation lines
            energy_match = re.search(r'energy\s*[=:]\s*(\d+)', line, re.IGNORECASE)
            mood_match = re.search(r'mood\s*[=:]\s*([^,\n]+)', line, re.IGNORECASE)
            
            if energy_match:
                current_energy = int(energy_match.group(1))
            if mood_match:
                current_mood = mood_match.group(1).strip()
    
    # Save last entry
    if current_idx is not None:
        results.append({'energy': current_energy, 'mood': current_mood})
    
    return results

# Test: prepare first batch
first_batch = needs_energy[:BATCH_SIZE]
batch_text = prepare_batch(first_batch)
print(f'\nSample batch ({len(first_batch)} songs):')
print(batch_text[:500])
print('...')

# Count how many batches we need
total_batches = (len(needs_energy) + BATCH_SIZE - 1) // BATCH_SIZE
print(f'\nTotal batches needed: {total_batches}')

# Save batch info for the subagent
batch_info = {
    'total_songs': len(songs),
    'needs_energy': len(needs_energy),
    'needs_mood': len(needs_mood),
    'needs_tempo': len(needs_tempo),
    'batch_size': BATCH_SIZE,
    'total_batches': total_batches,
    'sample_batch': batch_text[:1000],
}

with open(r'C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\classification-plan.json', 'w', encoding='utf-8') as f:
    json.dump(batch_info, f, ensure_ascii=False, indent=2)

print(f'\nClassification plan saved to classification-plan.json')
