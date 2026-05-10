import json
import random
import os
import re
import numpy as np
from google import genai
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'song-database-v1-classified.json')
KEYWORDS_PATH = os.path.join(os.path.dirname(__file__), 'keywords.txt')
EMBEDDINGS_PATH = os.path.join(os.path.dirname(__file__), 'song_embeddings.npz')
EMBEDDING_MODEL = 'models/gemini-embedding-001'
EMBEDDING_BONUS_MULTIPLIER = 2.0  # scale raw similarity scores to match +2/keyword system

class SongSelector:
    """Song selection algorithm for Radio Würmchen."""
    
    def __init__(self, db_path=DB_PATH, keywords_path=KEYWORDS_PATH):
        with open(db_path, 'r', encoding='utf-8') as f:
            self.songs = json.load(f)
        
        # Build index by titel_nr
        self.by_nr = {}
        for s in self.songs:
            self.by_nr[s['titel_nr']] = s
        self._db_path = db_path
        
        # Load keywords
        self.keywords = self._load_keywords(keywords_path)
        
        # Load song embeddings (semantic keyword matching)
        self._emb_matrix = None
        self._emb_titles = None
        self._emb_title_to_idx = {}
        if os.path.exists(EMBEDDINGS_PATH):
            try:
                data = np.load(EMBEDDINGS_PATH, allow_pickle=True)
                self._emb_matrix = data['embeddings']
                self._emb_titles = data['titles']
                self._emb_title_to_idx = {t: i for i, t in enumerate(self._emb_titles)}
                # Pre-normalize for faster cosine similarity
                norms = np.linalg.norm(self._emb_matrix, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                self._emb_normalized = self._emb_matrix / norms
                print(f"Loaded {len(self._emb_title_to_idx)} song embeddings ({self._emb_matrix.shape[1]}d)")
            except Exception as e:
                print(f"Could not load embeddings: {e}")
    
    def _load_keywords(self, path):
        """Load keywords from file. One keyword per line, case-insensitive."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                keywords = [line.strip().lower() for line in f if line.strip() and not line.strip().startswith('#')]
            return keywords
        except FileNotFoundError:
            return []
    
    def reload_keywords(self, path=KEYWORDS_PATH):
        """Reload keywords from file (for external updates without restart)."""
        self.keywords = self._load_keywords(path)
        # Clear cached keyword embeddings since keywords changed
        self._kw_emb_cache = getattr(self, '_kw_emb_cache', {})
        return len(self.keywords)
    
    def _compute_embedding_bonuses(self):
        """Compute embedding-based bonus for all songs against current keywords.
        
        Returns tuple (bonuses, per_keyword):
          bonuses: search_key ("Artist - Title") → bonus points (sum × multiplier)
          per_keyword: search_key → list of (keyword, similarity) pairs
        """
        if not self.keywords or self._emb_matrix is None:
            return {}, {}
        
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return {}, {}
        
        try:
            client = genai.Client(api_key=api_key)
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=[kw.lower() for kw in self.keywords],
            )
            kw_embeddings = np.array([emb.values for emb in result.embeddings], dtype=np.float32)
        except Exception as e:
            print(f"Warning: keyword embedding failed: {e}")
            return {}, {}
        
        # Normalize keyword embeddings for cosine similarity
        kw_norms = np.linalg.norm(kw_embeddings, axis=1, keepdims=True)
        kw_norms[kw_norms == 0] = 1.0
        kw_normalized = kw_embeddings / kw_norms
        
        # All-pairs cosine similarity: (n_songs, n_keywords)
        sim_matrix = self._emb_normalized @ kw_normalized.T
        
        # Sum similarities across all keywords for each song (Kurt's approach)
        sim_sums = np.sum(sim_matrix, axis=1)
        
        # Build result dicts: title_key → scaled bonus, title_key → per-kw breakdown
        bonuses = {}
        per_keyword = {}
        multiplier = EMBEDDING_BONUS_MULTIPLIER
        for i, title in enumerate(self._emb_titles):
            s = float(sim_sums[i])
            if s > 0.1:  # skip negligible matches
                bonuses[str(title)] = s * multiplier
                per_keyword[str(title)] = [
                    (self.keywords[j], float(sim_matrix[i, j]))
                    for j in range(len(self.keywords))
                ]
        
        return bonuses, per_keyword
    
    def mark_as_played(self, titel_nr):
        """Mark a song as played by updating rw_last_played in the database."""
        song = self.by_nr.get(titel_nr)
        if song:
            song['rw_last_played'] = datetime.now().isoformat()
            song['rw_play_count'] = song.get('rw_play_count', 0) + 1
            try:
                with open(self._db_path, 'w', encoding='utf-8') as f:
                    json.dump(self.songs, f, indent=2, ensure_ascii=False)
                return True
            except Exception:
                return False
        return False
    
    def find_by_filename(self, filename):
        """Find a song in the database by its filename. Returns the song dict or None."""
        filename_lower = os.path.basename(filename).lower()
        for song in self.songs:
            db_filename = song.get('filename', '')
            if db_filename and db_filename.lower() == filename_lower:
                return song
        return None
    
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
        
        # Pre-compute embedding-based bonuses for all songs (one API call + one matrix multiply)
        emb_bonuses, emb_per_kw = self._compute_embedding_bonuses() if self.keywords and self._emb_matrix is not None else ({}, {})
        
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
            
            # Keyword bonus: check artist and title against keyword list
            if self.keywords:
                search_text = f"{song.get('artist', '')} {song.get('title', '')}".lower()
                keyword_hits = 0
                for kw in self.keywords:
                    if re.search(r'\b' + re.escape(kw) + r'\b', search_text):
                        keyword_hits += 1
                if keyword_hits > 0:
                    score += keyword_hits * 2  # 2 points per keyword match
                    reasons.append(f'keywords:{keyword_hits}')
            
            # Embedding bonus: semantic similarity to all keywords (sum of cosine sims)
            if emb_bonuses:
                emb_key = f"{song.get('artist', '')} - {song.get('title', '')}"
                emb_bonus = emb_bonuses.get(emb_key, 0)
                if emb_bonus > 0:
                    score += emb_bonus
                    # Format per-keyword breakdown for the selected song
                    kw_details = emb_per_kw.get(emb_key, [])
                    if kw_details:
                        kw_str = ', '.join(f'{kw}:{sim:.2f}' for kw, sim in kw_details)
                        reasons.append(f'embed:{emb_bonus:.1f} ({kw_str})')
                    else:
                        reasons.append(f'embed:{emb_bonus:.1f}')
            
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
