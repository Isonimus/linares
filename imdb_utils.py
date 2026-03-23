"""
IMDb utilities for runtime movie operations.

This module provides:
- Movie search via IMDb suggestion API
- Movie details fetching (with local DB caching)
- Database save operations

Uses imdb_shared.py for common functionality.
"""

import urllib.request
import urllib.parse
import json
import sqlite3
import pandas as pd
from db import DB_PATH
from imdb_shared import (
    compute_embedding,
    fetch_full_movie_data,
)


def search_imdb_movies(title_search):
    """
    Search for movies using the unofficial IMDb suggestion API.
    
    This is faster than Cinemagoer's search and returns basic info
    suitable for autocomplete/search results.
    
    Args:
        title_search: Search query string
        
    Returns:
        list: Search results with id, title, year, type, image
    """
    try:
        query = urllib.parse.quote(title_search.lower())
        url = f"https://v3.sg.media-imdb.com/suggestion/x/{query}.json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=10)
        data = json.loads(res.read().decode('utf-8'))
        # 'q' indicates it's a media entity (movie/tv/video)
        return [m for m in data.get('d', []) if 'q' in m]
    except Exception as e:
        print(f"Error searching IMDb: {e}")
        return []


def get_movie_details(tconst):
    """
    Fetch full details for a movie, checking local DB cache first.
    
    If the movie exists in the local database, returns cached data.
    Otherwise, fetches from IMDb and caches the result.
    
    Args:
        tconst: IMDb title ID (e.g., 'tt0133093')
        
    Returns:
        dict: Complete movie data
    """
    # Check local DB first
    conn = sqlite3.connect(DB_PATH)
    query_db = "SELECT * FROM movies WHERE tconst = ?"
    db_movie = pd.read_sql_query(query_db, conn, params=[tconst])
    conn.close()

    if not db_movie.empty:
        row = db_movie.iloc[0]
        return {
            'tconst': tconst,
            'title': row['title'],
            'year': row['year'],
            'genres': row['genres'],
            'runtime': row['runtime'],
            'imdb_rating': row['imdb_rating'],
            'num_votes': row['num_votes'],
            'plot': row['plot'] if row['plot'] else "No synopsis available.",
            'directors': row['directors'] if row['directors'] else "Unknown",
            'writers': row['writers'] if row['writers'] else "Unknown",
            'actors': row['actors'] if row['actors'] else "Unknown",
            'poster_url': row.get('poster_url'),
            'plot_embedding': row.get('plot_embedding'),
            'composers': row.get('composers'),
            'certificates': row.get('certificates'),
            'languages': row.get('languages'),
            'countries': row.get('countries'),
            'keywords': row.get('keywords'),
            'source': "Local DB"
        }
    
    # Live fetch from IMDb
    print(f"Fetching data from IMDb live...")
    movie_data = fetch_full_movie_data(tconst, include_embedding=True)
    
    # Apply defaults for missing values
    movie_data['plot'] = movie_data['plot'] or "No synopsis available."
    movie_data['directors'] = movie_data['directors'] or "Unknown"
    movie_data['writers'] = movie_data['writers'] or "Unknown"
    movie_data['actors'] = movie_data['actors'] or "Unknown"
    movie_data['source'] = "IMDb Live"
    
    # Cache to local DB
    save_movie_to_db(movie_data)
    
    return movie_data


def save_movie_to_db(m):
    """
    Save or update a movie record in the local database.
    
    Uses INSERT OR REPLACE to handle both new inserts and updates.
    
    Args:
        m: Movie data dictionary
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO movies 
            (tconst, title, year, genres, runtime, imdb_rating, num_votes, 
             plot, directors, writers, actors, poster_url, plot_embedding, 
             composers, certificates, languages, countries, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            m['tconst'], m['title'], m.get('year'), m.get('genres'), 
            m.get('runtime'), m.get('imdb_rating'), m.get('num_votes'), 
            m.get('plot'), m.get('directors'), m.get('writers'), 
            m.get('actors'), m.get('poster_url'), m.get('plot_embedding'),
            m.get('composers'), m.get('certificates'), 
            m.get('languages'), m.get('countries'), m.get('keywords')
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error caching movie to DB: {e}")
