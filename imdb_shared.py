"""
Shared utilities for LINARES.

This module contains common functions used across:
- imdb_utils.py (runtime API queries)
- fetch_metadata.py (batch enrichment)

Movie metadata is fetched from The Movie Database (TMDB) API using IMDb IDs
as the lookup key via the /find endpoint.
"""

import urllib.request
import json
import numpy as np
from config import TMDB_API_KEY

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# Global embedder (lazy loaded, expensive to initialize)
_embedder = None


# =============================================================================
# Embedding Utilities
# =============================================================================

def get_embedder():
    """
    Get or create the sentence transformer embedder.

    Lazy-loaded because loading the model takes several seconds
    and isn't needed for all operations.
    """
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        print("Loading embedding model (all-MiniLM-L6-v2)...")
        _embedder = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedder


def compute_embedding(plot_text):
    """
    Compute a 384-dimensional embedding for a plot text.

    Args:
        plot_text: The movie plot/synopsis text

    Returns:
        bytes: The embedding as a binary blob (for SQLite storage), or None if invalid
    """
    if not plot_text or plot_text in ["No synopsis available.", "Error", ""]:
        return None
    embedder = get_embedder()
    embedding = embedder.encode([plot_text], show_progress_bar=False)[0]
    return embedding.astype(np.float32).tobytes()


# =============================================================================
# TMDB Fetching
# =============================================================================

def fetch_full_movie_data(tconst, include_embedding=True):
    """
    Fetch complete movie data from TMDB for a given tconst (IMDb ID).

    Args:
        tconst: The IMDb title ID (e.g., 'tt0133093')
        include_embedding: Whether to compute plot embedding (default True)

    Returns:
        dict: Complete movie data including optional embedding
    """
    # Step 1: resolve TMDB ID from IMDb ID
    find_url = f"{TMDB_BASE_URL}/find/{tconst}?external_source=imdb_id&api_key={TMDB_API_KEY}"
    req = urllib.request.Request(find_url, headers={'User-Agent': 'Mozilla/5.0'})
    find_data = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
    results = find_data.get('movie_results', [])
    if not results:
        raise ValueError(f"Movie {tconst} not found on TMDB")
    tmdb_id = results[0]['id']

    # Step 2: fetch full details in one call
    details_url = (
        f"{TMDB_BASE_URL}/movie/{tmdb_id}"
        f"?append_to_response=credits,keywords,release_dates&api_key={TMDB_API_KEY}"
    )
    req = urllib.request.Request(details_url, headers={'User-Agent': 'Mozilla/5.0'})
    movie = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())

    plot = movie.get('overview') or None
    poster_path = movie.get('poster_path')
    poster_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None

    langs = [l['english_name'] for l in movie.get('spoken_languages', [])]
    ctries = [c['name'] for c in movie.get('production_countries', [])]
    crew = movie.get('credits', {}).get('crew', [])
    cast = movie.get('credits', {}).get('cast', [])
    kw_list = [k['name'] for k in movie.get('keywords', {}).get('keywords', [])]

    certificates = None
    for rd in movie.get('release_dates', {}).get('results', []):
        if rd.get('iso_3166_1') == 'US':
            for r in rd.get('release_dates', []):
                cert = r.get('certification', '')
                if cert:
                    certificates = f'USA:{cert}'
                    break
            break

    data = {
        'tconst':       tconst,
        'title':        movie.get('title') or results[0].get('title'),
        'year':         int(movie['release_date'][:4]) if movie.get('release_date') else None,
        'genres':       ','.join(g['name'] for g in movie.get('genres', [])) or None,
        'runtime':      movie.get('runtime') or None,
        'imdb_rating':  movie.get('vote_average') or None,
        'num_votes':    movie.get('vote_count') or None,
        'plot':         plot,
        'poster_url':   poster_url,
        'directors':    ','.join(p['name'] for p in crew if p.get('job') == 'Director')[:200] or None,
        'writers':      ','.join(p['name'] for p in crew if p.get('department') == 'Writing')[:200] or None,
        'actors':          ','.join(p['name'] for p in cast[:10]) or None,
        'composers':       ','.join(p['name'] for p in crew if p.get('job') == 'Original Music Composer')[:200] or None,
        'certificates':    certificates,
        'languages':       ','.join(langs[:3]) or None,
        'countries':       ','.join(ctries[:3]) or None,
        'keywords':        ','.join(kw_list[:20]) or None,
        'collection_name': movie.get('belongs_to_collection', {}).get('name') if movie.get('belongs_to_collection') else None,
        'studios':         ','.join(c['name'] for c in movie.get('production_companies', [])[:5]) or None,
    }

    data['plot_embedding'] = compute_embedding(data['plot']) if include_embedding and data.get('plot') else None

    return data
