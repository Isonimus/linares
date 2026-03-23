"""
Batch metadata fetcher for LINARES.

This script fetches missing plots, posters, and other metadata for movies
in the database. It uses concurrent workers for efficiency and computes
plot embeddings for the ML model.

Usage:
    python fetch_metadata.py [limit] [--backfill] [--skip FIELDS]
    
    limit:      Maximum number of movies to process (default: 100)
    --backfill: Only process movies that already have plot/poster but are
                missing composers or certificates. Useful for enriching
                partially complete records without re-fetching everything.
    --skip:     Comma-separated list of fields to ignore when selecting
                movies. Movies whose ONLY missing fields are all in the
                skip list will not be processed. Useful for fields that
                IMDb rarely provides (e.g. composers).
                Valid fields: composers, certificates, languages,
                              countries, plot, poster_url

Examples:
    python fetch_metadata.py 500                          # Fetch 500 movies missing any data
    python fetch_metadata.py 1000 --backfill              # Backfill composers/certs for 1000 movies
    python fetch_metadata.py 500 --skip studios,composers # Skip movies only missing studios/composers

Uses the TMDB API (via IMDb ID lookup) for metadata fetching.
"""

import time
import random
import urllib.request
import json
from concurrent.futures import ThreadPoolExecutor
from db import get_connection, init_db
from config import TMDB_API_KEY
from imdb_shared import (
    get_embedder,
    compute_embedding,
)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


def fetch_movie_metadata(movie_tuple):
    """
    Fetch metadata for a single movie.
    
    This function is designed to be called concurrently by ThreadPoolExecutor.
    
    Args:
        movie_tuple: (tconst, title) tuple
        
    Returns:
        dict: Fetched metadata with 'status' key indicating success/error
    """
    tconst, title = movie_tuple
    try:
        # Step 1: resolve TMDB ID from IMDb ID
        find_url = f"{TMDB_BASE_URL}/find/{tconst}?external_source=imdb_id&api_key={TMDB_API_KEY}"
        req = urllib.request.Request(find_url, headers={'User-Agent': 'Mozilla/5.0'})
        find_data = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        results = find_data.get('movie_results', [])
        if not results:
            return {'tconst': tconst, 'title': title, 'status': 'error', 'error': 'Not found on TMDB'}
        tmdb_id = results[0]['id']

        # Step 2: fetch full details in one call
        details_url = (
            f"{TMDB_BASE_URL}/movie/{tmdb_id}"
            f"?append_to_response=credits,keywords,release_dates&api_key={TMDB_API_KEY}"
        )
        req = urllib.request.Request(details_url, headers={'User-Agent': 'Mozilla/5.0'})
        movie = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())

        # Plot
        plot = movie.get('overview') or None

        # Poster
        poster_path = movie.get('poster_path')
        poster_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None

        # Languages / countries
        langs = [l['english_name'] for l in movie.get('spoken_languages', [])]
        languages = ','.join(langs[:3]) or None
        ctries = [c['name'] for c in movie.get('production_countries', [])]
        countries = ','.join(ctries[:3]) or None

        # Credits
        crew = movie.get('credits', {}).get('crew', [])
        cast = movie.get('credits', {}).get('cast', [])
        directors  = ','.join(p['name'] for p in crew if p.get('job') == 'Director')[:200] or None
        writers    = ','.join(p['name'] for p in crew if p.get('department') == 'Writing')[:200] or None
        actors     = ','.join(p['name'] for p in cast[:10]) or None
        composers  = ','.join(p['name'] for p in crew if p.get('job') == 'Original Music Composer')[:200] or None

        # Keywords
        kw_list = [k['name'] for k in movie.get('keywords', {}).get('keywords', [])]
        keywords = ','.join(kw_list[:20]) or None

        # Franchise / studios
        collection = movie.get('belongs_to_collection')
        collection_name = collection.get('name') if collection else None
        studios = ','.join(c['name'] for c in movie.get('production_companies', [])[:5]) or None

        # US certificate (formatted to match existing extract_certificate_mppa expectations)
        certificates = None
        for rd in movie.get('release_dates', {}).get('results', []):
            if rd.get('iso_3166_1') == 'US':
                for r in rd.get('release_dates', []):
                    cert = r.get('certification', '')
                    if cert:
                        certificates = f'USA:{cert}'
                        break
                break

        time.sleep(random.uniform(0.5, 1.0))

        return {
            'tconst': tconst,
            'title': title,
            'plot': plot,
            'poster_url': poster_url,
            'languages': languages,
            'countries': countries,
            'directors': directors,
            'writers': writers,
            'actors': actors,
            'composers': composers,
            'keywords': keywords,
            'certificates': certificates,
            'collection_name': collection_name,
            'studios': studios,
            'status': 'success',
        }
    except Exception as e:
        print(f"Error fetching '{title}' ({tconst}): {e}")
        return {'tconst': tconst, 'title': title, 'status': 'error', 'error': str(e)}


# All skippable metadata fields and their corresponding DB columns
SKIPPABLE_FIELDS = {
    'composers', 'certificates', 'languages', 'countries',
    'plot', 'poster_url', 'keywords', 'collection_name', 'studios',
}


def run_metadata_enrichment(limit=None, batch_size=50, backfill_only=False, skip_fields=None):
    """
    Run batch metadata enrichment for movies missing data.
    
    Targets movies that are missing essential fields (plot/poster) OR 
    ML feature fields (composers, certificates, languages, countries).
    
    Args:
        limit: Maximum number of movies to process
        batch_size: Commit to database every N movies
        backfill_only: If True, only process movies that have plot/poster but missing ML fields
        skip_fields: Set of field names to ignore when selecting movies.
                     Movies whose only missing fields are all in this set
                     are excluded from processing.
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Helper macro for checking missing values (NULL, empty, 'Unknown', or 'None' string)
    def missing_check(col):
        return f"({col} IS NULL OR {col} = '' OR {col} = 'Unknown' OR {col} = 'None')"
    
    skip_fields = skip_fields or set()
    
    # Define all checkable field conditions
    field_conditions = {
        'plot':         "(plot IS NULL OR plot = '' OR plot = 'No synopsis available.')",
        'poster_url':   "(poster_url IS NULL OR poster_url = '' OR poster_url LIKE '%placeholder%')",
        'composers':    missing_check('composers'),
        'certificates': missing_check('certificates'),
        'languages':    missing_check('languages'),
        'countries':    missing_check('countries'),
        'keywords':         missing_check('keywords'),
        'collection_name':  missing_check('collection_name'),
        'studios':          missing_check('studios'),
    }
    
    if backfill_only:
        # Target movies that HAVE plot/poster but are missing ML feature fields
        ml_fields = ['composers', 'certificates', 'languages', 'countries', 'keywords']
        active_ml = [f for f in ml_fields if f not in skip_fields]
        if not active_ml:
            print("All ML fields are in the skip list — nothing to backfill.")
            conn.close()
            return
        ml_or = " OR ".join(field_conditions[f] for f in active_ml)
        query = f"""
            SELECT tconst, title FROM movies 
            WHERE plot IS NOT NULL AND plot != '' AND plot != 'No synopsis available.'
              AND ({ml_or})
            ORDER BY num_votes DESC
        """
    else:
        # Active fields = all fields minus skipped ones
        active_fields = [f for f in field_conditions if f not in skip_fields]
        if not active_fields:
            print("All fields are in the skip list — nothing to fetch.")
            conn.close()
            return
        where_or = " OR ".join(field_conditions[f] for f in active_fields)
        query = f"""
            SELECT tconst, title FROM movies 
            WHERE {where_or}
            ORDER BY num_votes DESC
        """
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    movies_to_process = cursor.fetchall()
    
    if not movies_to_process:
        print("All movies in database already have metadata!")
        conn.close()
        return

    total = len(movies_to_process)
    print(f"Starting enrichment for {total} movies...")
    
    # Pre-warm embedder (takes a few seconds to load)
    get_embedder()
    
    processed = 0
    success_count = 0
    
    # Helper to check if a value is "missing"
    def is_missing(val):
        return val is None or val == '' or val == 'Unknown' or val == 'None' or val == 'No synopsis available.'
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = executor.map(fetch_movie_metadata, movies_to_process)
        
        for res in results:
            processed += 1
            
            if res['status'] == 'success':
                tconst = res['tconst']
                
                # Get current values from DB to compare
                cursor.execute("""
                    SELECT plot, poster_url, composers, certificates, languages, countries, keywords,
                           collection_name, studios
                    FROM movies WHERE tconst = ?
                """, (tconst,))
                current = cursor.fetchone()
                old_plot, old_poster, old_composers, old_certs, old_langs, old_countries, old_keywords, old_collection, old_studios = current or (None,)*9

                # New values from fetch
                new_plot = res.get('plot')
                new_poster = res.get('poster_url')
                new_composers = res.get('composers')
                new_certs = res.get('certificates')
                new_langs = res.get('languages')
                new_countries = res.get('countries')
                new_keywords = res.get('keywords')
                new_collection = res.get('collection_name')
                new_studios = res.get('studios')
                
                # Build a conditional UPDATE: only set fields where the
                # new value is non-missing (avoids overwriting good data
                # with None when IMDb simply doesn't have that field).
                updates = []
                params  = []
                filled  = []   # for the progress log
                
                def maybe_update(col, old_val, new_val, label):
                    """Queue an UPDATE SET clause if new_val is non-missing."""
                    if new_val and not is_missing(new_val):
                        updates.append(f"{col} = ?")
                        params.append(new_val)
                        if is_missing(old_val):
                            filled.append(label)
                
                maybe_update('plot',         old_plot,      new_plot,      'Plot')
                maybe_update('poster_url',   old_poster,    new_poster,    'Poster')
                maybe_update('composers',    old_composers, new_composers, 'Composers')
                maybe_update('certificates', old_certs,     new_certs,     'Certs')
                maybe_update('languages',    old_langs,     new_langs,     'Lang')
                maybe_update('countries',    old_countries,  new_countries, 'Country')
                maybe_update('keywords',        old_keywords,   new_keywords,   'Keywords')
                maybe_update('collection_name', old_collection, new_collection, 'Collection')
                maybe_update('studios',         old_studios,    new_studios,    'Studios')
                
                # Compute embedding only when we have a (new) plot value
                if new_plot and not is_missing(new_plot):
                    embedding_blob = compute_embedding(new_plot)
                    if embedding_blob:
                        updates.append('plot_embedding = ?')
                        params.append(embedding_blob)
                
                if updates:
                    params.append(tconst)
                    cursor.execute(
                        f"UPDATE movies SET {', '.join(updates)} WHERE tconst = ?",
                        tuple(params),
                    )
                    success_count += 1
                
                filled_str = ', '.join(filled) if filled else '(no new data)'
                print(f"[{processed}/{total}] {res.get('title', '?')[:40]:40} | {filled_str}")
                
                # Commit in batches for efficiency
                if processed % batch_size == 0:
                    conn.commit()
                    print(f"Progress: {processed}/{total} movies processed...")

    conn.commit()
    conn.close()
    print(f"\n✅ Enrichment complete! {success_count}/{processed} movies updated successfully.")


if __name__ == "__main__":
    import sys
    
    fetch_limit = 100
    backfill_mode = False
    skip_set = set()
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--backfill':
            backfill_mode = True
        elif arg == '--skip':
            i += 1
            if i >= len(args):
                print("Error: --skip requires a comma-separated list of fields.")
                print(f"Valid fields: {', '.join(sorted(SKIPPABLE_FIELDS))}")
                sys.exit(1)
            raw = {f.strip().lower() for f in args[i].split(',') if f.strip()}
            invalid = raw - SKIPPABLE_FIELDS
            if invalid:
                print(f"Error: unknown skip field(s): {', '.join(sorted(invalid))}")
                print(f"Valid fields: {', '.join(sorted(SKIPPABLE_FIELDS))}")
                sys.exit(1)
            skip_set = raw
        elif arg.isdigit():
            fetch_limit = int(arg)
        elif arg in ['-h', '--help']:
            print("Usage: python fetch_metadata.py [limit] [--backfill] [--skip FIELDS]")
            print("")
            print("  limit       Maximum number of movies to process (default: 100)")
            print("  --backfill  Only process movies that have plot/poster but missing")
            print("              composers or certificates (skip fully missing movies)")
            print("  --skip      Comma-separated fields to ignore when selecting movies.")
            print("              Movies whose only missing fields are all skipped will")
            print("              not be processed. Avoids wasted fetches for data that")
            print("              IMDb rarely provides.")
            print(f"              Valid fields: {', '.join(sorted(SKIPPABLE_FIELDS))}")
            sys.exit(0)
        i += 1
    
    if backfill_mode:
        print("Running in BACKFILL mode (only partially enriched movies)...")
    if skip_set:
        print(f"Skipping movies whose only missing fields are: {', '.join(sorted(skip_set))}")
    
    run_metadata_enrichment(limit=fetch_limit, backfill_only=backfill_mode, skip_fields=skip_set)
