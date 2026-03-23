"""
Initial database setup for LINARES.

This script downloads IMDb's public datasets and populates the local database
with popular movies (10k+ votes). It also fetches plots and posters for the
top 1000 movies to enable immediate use.

This is a one-time setup script. For incremental updates, use fetch_metadata.py.

Usage:
    python setup_database.py
"""

import os
import gzip
import csv
import urllib.request
import logging
import time
from db import init_db, get_connection
from config import MIN_VOTES, SETUP_FETCH_LIMIT

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# IMDb dataset URLs
RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
BASICS_URL = "https://datasets.imdbws.com/title.basics.tsv.gz"
CREW_URL = "https://datasets.imdbws.com/title.crew.tsv.gz"
PRINCIPALS_URL = "https://datasets.imdbws.com/title.principals.tsv.gz"
NAMES_URL = "https://datasets.imdbws.com/name.basics.tsv.gz"



def get_stream(url):
    """Open a gzipped remote file as a stream."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib.request.urlopen(req)
    return gzip.GzipFile(fileobj=response)


def download_and_process():
    """
    Download IMDb datasets and populate the database.
    
    This function:
    1. Downloads ratings to identify popular movies (10k+ votes)
    2. Downloads crew data (directors, writers)
    3. Downloads principals data (cast)
    4. Downloads names to resolve person IDs to names
    5. Downloads basics and inserts movies into database
    6. Fetches plots/posters for top 1000 movies
    """
    logging.info("Initializing database...")
    init_db()
    
    # Step 1: Get popular movies from ratings
    valid_movies = {}
    logging.info(f"Step 1: Downloading IMDb Ratings...")
    with get_stream(RATINGS_URL) as uncompressed:
        decoded = (line.decode('utf-8') for line in uncompressed)
        reader = csv.reader(decoded, delimiter='\t')
        next(reader)  # Skip header
        for row in reader:
            try:
                tconst, rating, votes = row
                v = int(votes)
                if v >= MIN_VOTES:
                    valid_movies[tconst] = {
                        "rating": float(rating), 
                        "votes": v, 
                        "crew": {"directors": [], "writers": [], "actors": []}
                    }
            except:
                pass
    
    logging.info(f"Found {len(valid_movies)} popular movies.")

    # Step 2: Get crew (directors & writers)
    logging.info("Step 2: Processing Crew (Directors & Writers)...")
    with get_stream(CREW_URL) as uncompressed:
        decoded = (line.decode('utf-8') for line in uncompressed)
        reader = csv.reader(decoded, delimiter='\t')
        next(reader)
        for row in reader:
            tconst, directors, writers = row
            if tconst in valid_movies:
                if directors != '\\N': 
                    valid_movies[tconst]["crew"]["directors"] = directors.split(',')
                if writers != '\\N': 
                    valid_movies[tconst]["crew"]["writers"] = writers.split(',')

    # Step 3: Get principals (cast)
    logging.info("Step 3: Processing Principals (Cast)...")
    with get_stream(PRINCIPALS_URL) as uncompressed:
        decoded = (line.decode('utf-8') for line in uncompressed)
        reader = csv.reader(decoded, delimiter='\t')
        next(reader)
        for row in reader:
            tconst, ordering, nconst, category, job, characters = row[:6]
            if tconst in valid_movies and category in ('actor', 'actress', 'self'):
                valid_movies[tconst]["crew"]["actors"].append(nconst)

    # Step 4: Resolve person IDs to names
    required_nconsts = set()
    for m in valid_movies.values():
        required_nconsts.update(m["crew"]["directors"])
        required_nconsts.update(m["crew"]["writers"])
        required_nconsts.update(m["crew"]["actors"])
    
    logging.info(f"Step 4: Resolving names for {len(required_nconsts)} people...")
    name_map = {}
    with get_stream(NAMES_URL) as uncompressed:
        decoded = (line.decode('utf-8') for line in uncompressed)
        reader = csv.reader(decoded, delimiter='\t')
        next(reader)
        for row in reader:
            nconst, primaryName = row[0], row[1]
            if nconst in required_nconsts:
                name_map[nconst] = primaryName
    
    # Step 5: Process basics and insert into database
    logging.info("Step 5: Final processing of Basics and DB Ingestion...")
    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    
    with get_stream(BASICS_URL) as uncompressed:
        decoded = (line.decode('utf-8') for line in uncompressed)
        reader = csv.reader(decoded, delimiter='\t')
        next(reader)
        for row in reader:
            if len(row) < 9:
                continue
            tconst, titleType, primaryTitle, originalTitle, isAdult, startYear, endYear, runtimeMinutes, genres = row[:9]
            
            if tconst in valid_movies and titleType == 'movie':
                m_data = valid_movies[tconst]
                year = int(startYear) if startYear != '\\N' else None
                runtime = int(runtimeMinutes) if runtimeMinutes != '\\N' else None
                
                # Resolve person IDs to names
                d_names = ",".join([name_map.get(nid, nid) for nid in m_data["crew"]["directors"]])
                w_names = ",".join([name_map.get(nid, nid) for nid in m_data["crew"]["writers"]])
                a_names = ",".join([name_map.get(nid, nid) for nid in m_data["crew"]["actors"]])

                cursor.execute('''
                    INSERT OR REPLACE INTO movies 
                    (tconst, title, year, genres, runtime, imdb_rating, num_votes, directors, writers, actors, poster_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tconst, primaryTitle, year, genres, runtime, 
                    m_data["rating"], m_data["votes"], 
                    d_names or None, w_names or None, a_names or None, 
                    None
                ))
                
                count += 1
                if count % 1000 == 0:
                    conn.commit()
                    logging.info(f"  Inserted {count} movies...")
    
    conn.commit()
    logging.info(f"Inserted {count} movies into database.")
    
    # Step 6: Fetch plots and posters for top movies
    logging.info(f"Step 6: Fetching Plots and Posters for top {SETUP_FETCH_LIMIT} movies...")
    logging.info("  (Remaining movies can be processed later via fetch_metadata.py)")

    ia = get_cinemagoer()
    cursor.execute(f"""
        SELECT tconst FROM movies
        WHERE plot IS NULL AND poster_url IS NULL
        ORDER BY num_votes DESC
        LIMIT {SETUP_FETCH_LIMIT}
    """)
    targets = cursor.fetchall()
    
    for i, (tconst,) in enumerate(targets):
        try:
            movie = ia.get_movie(tconst[2:])  # Remove 'tt' prefix
            ia.update(movie, ['plot', 'main'])
            
            plots = movie.get('plot', [])
            plot = plots[0].split('::')[0] if plots else None
            poster = movie.get('full-size cover url') or movie.get('cover url')
            
            cursor.execute(
                "UPDATE movies SET plot = ?, poster_url = ? WHERE tconst = ?", 
                (plot, poster, tconst)
            )
            conn.commit()
            
            if (i + 1) % 100 == 0:
                logging.info(f"  Fetched {i + 1}/{len(targets)} movies...")
            
            time.sleep(0.5)  # Rate limiting
        except Exception as e:
            logging.error(f"Error fetching {tconst}: {e}")

    conn.close()
    logging.info(f"Setup complete! {count} movies in database.")


if __name__ == "__main__":
    download_and_process()
