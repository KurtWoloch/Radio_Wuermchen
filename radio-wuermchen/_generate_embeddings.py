"""Generate text embeddings for all songs in the Radio Würmchen library.

One-time script. Saves to song_embeddings.npz for fast lookup by song_selector.py.
Uses Google text-embedding-004 (same GEMINI_API_KEY as dj_brain).
Estimated cost: ~$0.02 for entire library at current pricing.

Usage: py _generate_embeddings.py
"""

import json
import os
import sys
import time
import numpy as np
from google import genai

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, 'song-database-v1-classified.json')
OUT_PATH = os.path.join(SCRIPT_DIR, 'song_embeddings.npz')
EMBEDDING_MODEL = 'models/gemini-embedding-001'
BATCH_SIZE = 500  # texts per API call


def main():
    # Load songs
    print(f"Loading song database...")
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        songs = json.load(f)
    
    print(f"Found {len(songs)} songs.")
    
    # Build title keys
    titles = []
    for s in songs:
        artist = s.get('artist', '').strip()
        title = s.get('title', '').strip()
        titles.append(f"{artist} - {title}")
    
    # Check API key
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)
    
    client = genai.Client(api_key=api_key)
    
    # Test one call to get embedding dimension
    print(f"Testing embedding model: {EMBEDDING_MODEL}...")
    try:
        test_result = client.models.embed_content(model=EMBEDDING_MODEL, contents=["test"])
        emb_dim = len(test_result.embeddings[0].values)
        print(f"Embedding dimension: {emb_dim}")
    except Exception as e:
        print(f"ERROR: Cannot use embedding model: {e}")
        sys.exit(1)
    
    # Generate embeddings in batches
    all_embeddings = []
    n_batches = (len(titles) + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"Generating embeddings in {n_batches} batches of {BATCH_SIZE}...")
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Estimated cost: ~${len(titles) * 0.000000025:.4f} (at $0.000025/1K chars)")
    
    t_start = time.time()
    
    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        
        try:
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch,
            )
            for emb in result.embeddings:
                all_embeddings.append(emb.values)
            
            elapsed = time.time() - t_start
            progress = min(i + BATCH_SIZE, len(titles))
            eta = (elapsed / progress) * (len(titles) - progress) if progress > 0 else 0
            print(f"  Batch {batch_num}/{n_batches}: {progress}/{len(titles)} songs "
                  f"({elapsed:.0f}s elapsed, ETA {eta:.0f}s)")
            
        except Exception as e:
            print(f"  ERROR in batch {batch_num}: {e}")
            # Retry one-by-one for this batch
            print(f"  Retrying one at a time...")
            for text in batch:
                try:
                    result = client.models.embed_content(
                        model=EMBEDDING_MODEL,
                        contents=[text],
                    )
                    all_embeddings.append(result.embeddings[0].values)
                except Exception as e2:
                    print(f"    FAILED: {text[:60]}... -> {e2}")
                    # Zero vector as fallback
                    all_embeddings.append([0.0] * emb_dim)
            print(f"  Batch {batch_num} recovered.")
        
        # Rate limit: small delay between batches
        if i + BATCH_SIZE < len(titles):
            time.sleep(0.1)
    
    total_time = time.time() - t_start
    print(f"\nDone! {len(all_embeddings)} embeddings in {total_time:.0f}s")
    
    # Convert to numpy array
    embeddings_matrix = np.array(all_embeddings, dtype=np.float32)
    titles_array = np.array(titles, dtype=str)
    
    print(f"Embedding matrix: {embeddings_matrix.shape}")
    print(f"dtype: {embeddings_matrix.dtype}")
    print(f"Memory: {embeddings_matrix.nbytes / 1024 / 1024:.1f} MB")
    
    # Save
    np.savez_compressed(OUT_PATH, titles=titles_array, embeddings=embeddings_matrix)
    file_size = os.path.getsize(OUT_PATH) / 1024 / 1024
    print(f"Saved to: {OUT_PATH} ({file_size:.1f} MB)")


if __name__ == '__main__':
    main()
