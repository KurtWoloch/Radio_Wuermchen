import json
import random
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'song-database-v1-classified.json')

class SongSelector:
    """Song selection algorithm for Radio Würmchen."""
    
    def __init__(self, db_path=DB_PATH):
        with open(db_path, 'r', encoding='utf-8') as f:
            self.songs = json.load(f)
        
        # Build index by titel_nr
        self.by_nr = {}
        for s in self.songs:
            self.by_nr[s['titel_nr']] = s
    
    def select(self, 
               energy_target=5, 
               mood_target=None, 
               genre_prefer=None,
               exclude_nrs=None, 
               exclude_hours=2,
               kurt_min_rating=None,
               pool_nrs=None,
               pool_bonus=2,
               count=1):
        """
        Select songs based on criteria.
        
        Args:
            energy_target: Target energy level (1-10)
            mood_target: Target mood string (optional)
            genre_prefer: Preferred genre tags (optional, list)
            exclude_nrs: Set of Titel_Nr to exclude (recent plays)
            exclude_hours: Minimum hours since last play (for RW)
            kurt_min_rating: Minimum Kurt rating (0-40, optional)
            pool_nrs: Set of Titel_Nr in suggestion pool (bonus applied)
            pool_bonus: Bonus points for pool songs
            count: Number of songs to select
        
        Returns:
            List of selected song dicts
        """
        if exclude_nrs is None:
            exclude_nrs = set()
        
        # Calculate cutoff time for recent plays
        cutoff = None
        if exclude_hours:
            cutoff = (datetime.now() - timedelta(hours=exclude_hours)).isoformat()
        
        candidates = []
        
        for song in self.songs:
            tn = song['titel_nr']
            
            # Exclude recent plays
            if tn in exclude_nrs:
                continue
            if cutoff and song.get('rw_last_played') and song['rw_last_played'] > cutoff:
                continue
            
            # Filter by minimum rating
            if kurt_min_rating is not None:
                rating = song.get('kurt_rating')
                if rating is None or rating < kurt_min_rating:
                    continue
            
            # Calculate score
            score = 0
            reasons = []
            
            # Energy distance (lower is better)
            energy = song.get('energy')
            if energy is not None:
                energy_dist = abs(energy - energy_target)
                energy_score = max(0, 10 - energy_dist * 2)
                score += energy_score
                if energy_dist <= 1:
                    reasons.append('energy_match')
            
            # Mood match
            if mood_target and song.get('mood'):
                if song['mood'].lower() == mood_target.lower():
                    score += 3
                    reasons.append('mood_match')
            
            # Genre preference
            if genre_prefer:
                song_genres = [g.lower() for g in song.get('genre_tags', [])]
                matching_genres = sum(1 for g in genre_prefer if g.lower() in song_genres)
                if matching_genres > 0:
                    score += matching_genres * 2
                    reasons.append('genre_match')
            
            # Kurt rating bonus
            rating = song.get('kurt_rating')
            if rating is not None:
                # Normalize 0-40 to 0-5 bonus
                rating_bonus = (rating / 40) * 5
                score += rating_bonus
                if rating >= 30:
                    reasons.append('high_rating')
            
            # Bekanntheit bonus (prefer songs Kurt knows)
            bek = song.get('bekanntheit')
            if bek:
                try:
                    bek_val = float(bek.replace(',', '.'))
                    if bek_val <= 2.0:
                        score += 2
                        reasons.append('well_known')
                    elif bek_val <= 3.0:
                        score += 1
                        reasons.append('known')
                except:
                    pass
            
            # Pool bonus
            if pool_nrs and tn in pool_nrs:
                score += pool_bonus
                reasons.append('in_pool')
            
            # Recency bonus (never played = slight bonus)
            if not song.get('rw_last_played'):
                score += 0.5
                reasons.append('never_played')
            
            # Decade variation bonus (randomized)
            if random.random() < 0.1:
                score += 1
                reasons.append('variety_bonus')
            
            candidates.append({
                'song': song,
                'score': score,
                'reasons': reasons,
            })
        
        if not candidates:
            return []
        
        # Sort by score descending
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Select from top candidates using weighted random
        top_n = min(20, len(candidates))
        top_candidates = candidates[:top_n]
        
        # Weight by score
        weights = [c['score'] + 1 for c in top_candidates]  # +1 to avoid zero weights
        total_weight = sum(weights)
        
        selected = []
        used_nrs = set()
        
        for _ in range(count):
            if not top_candidates:
                break
            
            # Weighted random selection
            r = random.uniform(0, total_weight)
            cumulative = 0
            for i, (candidate, weight) in enumerate(zip(top_candidates, weights)):
                cumulative += weight
                if cumulative >= r:
                    song = candidate['song']
                    if song['titel_nr'] not in used_nrs:
                        selected.append({
                            'titel_nr': song['titel_nr'],
                            'filename': song.get('filename'),
                            'artist': song.get('artist'),
                            'title': song.get('title'),
                            'energy': song.get('energy'),
                            'mood': song.get('mood'),
                            'tempo_bpm': song.get('tempo_bpm'),
                            'score': round(candidate['score'], 2),
                            'reasons': candidate['reasons'],
                        })
                        used_nrs.add(song['titel_nr'])
                        total_weight -= weight
                        top_candidates.pop(i)
                        weights.pop(i)
                    break
        
        return selected

# === Test the selector ===
if __name__ == '__main__':
    selector = SongSelector()
    
    print('\n=== Test 1: Pop songs, energy 5 ===')
    results = selector.select(energy_target=5, genre_prefer=['Pop'], count=5)
    for r in results:
        print(f"  {r['artist']} - {r['title']} (energy={r['energy']}, score={r['score']}, {r['reasons']})")
    
    print('\n=== Test 2: Rock songs, energy 7 ===')
    results = selector.select(energy_target=7, genre_prefer=['Rock'], count=5)
    for r in results:
        print(f"  {r['artist']} - {r['title']} (energy={r['energy']}, score={r['score']}, {r['reasons']})")
    
    print('\n=== Test 3: Calm songs, energy 3 ===')
    results = selector.select(energy_target=3, count=5)
    for r in results:
        print(f"  {r['artist']} - {r['title']} (energy={r['energy']}, score={r['score']}, {r['reasons']})")
    
    print('\n=== Test 4: High-rated songs only (>=30) ===')
    results = selector.select(kurt_min_rating=30, count=5)
    for r in results:
        print(f"  {r['artist']} - {r['title']} (energy={r['energy']}, score={r['score']}, {r['reasons']})")
