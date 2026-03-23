"""
FastAPI REST API for LINARES movie predictor.

Updated to use the improved feature engineering pipeline.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, model_validator
from typing import List, Optional
import sqlite3
import pandas as pd
import numpy as np
import os
import logging
import config

logger = logging.getLogger(__name__)
from db import DB_PATH, DATA_DIR
from imdb_utils import search_imdb_movies, get_movie_details
from features import FeatureMetadata, extract_embedding
from catboost import CatBoostRegressor

app = FastAPI(title="LINARES API")

# CORS — configurable via ALLOWED_ORIGINS env var (comma-separated list).
# Defaults to "*" for local use. Set a specific origin for non-local deployments,
# e.g. ALLOWED_ORIGINS=http://localhost:5173,https://yourdomain.com
_origins_env = os.environ.get("ALLOWED_ORIGINS", "*")
allowed_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_data(data):
    """Recursively convert NaN/NaT to None for Pydantic/JSON validation."""
    if isinstance(data, list):
        return [clean_data(i) for i in data]
    if isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items()}
    
    # Use pd.isna for all missing types (nan, None, pd.NA)
    try:
        if pd.isna(data):
            return None
    except Exception:
        pass

    # Ensure standard floats/ints for JSON compliance
    if isinstance(data, (float, np.float32, np.float64)):
        if np.isnan(data) or np.isinf(data):
            return None
        return float(data)
    
    # Specific check for common "nan" string-like objects if any
    if str(data) == 'nan':
        return None
        
    return data

# Cache for loaded models and metadata
_model_cache = {}


class User(BaseModel):
    id: int
    name: str


class Movie(BaseModel):
    tconst: str
    title: str
    year: Optional[int] = None
    genres: Optional[str] = None
    runtime: Optional[int] = None
    imdb_rating: Optional[float] = None
    directors: Optional[str] = None
    actors: Optional[str] = None
    plot: Optional[str] = None
    poster_url: Optional[str] = None
    composers: Optional[str] = None
    certificates: Optional[str] = None
    languages: Optional[str] = None
    countries: Optional[str] = None
    keywords: Optional[str] = None
    collection_name: Optional[str] = None
    studios: Optional[str] = None
    predicted_score: Optional[float] = None
    rating_label: Optional[str] = None
    rating_score: Optional[float] = None

    @model_validator(mode='before')
    @classmethod
    def clean_nan_to_none(cls, data):
        """Final safety net: convert NaN values in input dict to None."""
        if isinstance(data, dict):
            return {k: (None if pd.isna(v) or (isinstance(v, float) and np.isnan(v)) else v) for k, v in data.items()}
        return data


class SearchResult(BaseModel):
    id: str
    l: str
    y: Optional[int] = None
    q: Optional[str] = None
    i: Optional[dict] = None
    rating_label: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def clean_nan_to_none(cls, data):
        """Final safety net: convert NaN values in input dict to None."""
        if isinstance(data, dict):
            return {k: (None if pd.isna(v) or (isinstance(v, float) and np.isnan(v)) else v) for k, v in data.items()}
        return data


def load_user_model(username: str):
    """Load model and metadata for a user, with caching."""
    cache_key = username.lower()
    
    if cache_key in _model_cache:
        return _model_cache[cache_key]
    
    model_path = os.path.join(DATA_DIR, f'model_{username}.cbm')
    metadata_path = os.path.join(DATA_DIR, f'model_{username}_metadata.json')
    
    if not os.path.exists(model_path):
        return None, None
    
    model = CatBoostRegressor()
    model.load_model(model_path)
    metadata = FeatureMetadata.load(metadata_path)
    
    _model_cache[cache_key] = (model, metadata)
    return model, metadata


@app.get("/users", response_model=List[User])
def get_users():
    conn = sqlite3.connect(DB_PATH)
    users_df = pd.read_sql_query("SELECT id, name FROM users", conn)
    conn.close()
    return clean_data(users_df.to_dict(orient="records"))


@app.get("/config/ratings")
def get_rating_config():
    return config.RATING_SCALE


@app.get("/search", response_model=List[SearchResult])
def search_movies(q: str, offset: int = 0, limit: int = 20, username: Optional[str] = None):
    results = search_imdb_movies(q)
    
    if username:
        conn = sqlite3.connect(DB_PATH)
        user_df = pd.read_sql_query("SELECT id FROM users WHERE LOWER(name) = ?", conn, params=[username.lower()])
        if not user_df.empty:
            user_id = user_df.iloc[0]['id']
            cursor = conn.cursor()
            cursor.execute("SELECT movie_tconst, rating_label FROM ratings WHERE user_id = ?", (int(user_id),))
            ratings_map = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()

            for r in results:
                if r['id'] in ratings_map:
                    r['rating_label'] = ratings_map[r['id']]
        else:
            conn.close()

    # Apply pagination to search results
    return results[offset : offset + limit]


@app.get("/movie/{tconst}", response_model=Movie)
def get_movie(tconst: str, username: Optional[str] = None):
    try:
        details = get_movie_details(tconst)
        if username:
            conn = sqlite3.connect(DB_PATH)
            user_df = pd.read_sql_query("SELECT id FROM users WHERE LOWER(name) = ?", conn, params=[username.lower()])
            if not user_df.empty:
                user_id = user_df.iloc[0]['id']
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT rating_label, rating_score FROM ratings WHERE user_id = ? AND movie_tconst = ?",
                    (int(user_id), tconst)
                )
                row = cursor.fetchone()
                if row:
                    details['rating_label'] = row[0]
                    details['rating_score'] = row[1]
            conn.close()
        return clean_data(details)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/similar/{tconst}", response_model=List[Movie])
def get_similar_movies(tconst: str, limit: int = 12, username: Optional[str] = None):
    """Return movies with the most similar plot embeddings to the given tconst."""
    conn = sqlite3.connect(DB_PATH)

    # Load seed embedding
    seed_row = pd.read_sql_query(
        "SELECT plot_embedding FROM movies WHERE tconst = ?", conn, params=[tconst]
    )
    if seed_row.empty or seed_row.iloc[0]['plot_embedding'] is None:
        conn.close()
        raise HTTPException(status_code=404, detail="No plot embedding available for this movie")

    seed_emb = extract_embedding(seed_row.iloc[0]['plot_embedding'])
    seed_norm = seed_emb / (np.linalg.norm(seed_emb) + 1e-8)

    # Load all other movies that have embeddings
    df = pd.read_sql_query("""
        SELECT tconst, title, year, genres, runtime, imdb_rating, num_votes,
               directors, actors, plot, poster_url, plot_embedding
        FROM movies
        WHERE plot_embedding IS NOT NULL AND tconst != ?
    """, conn, params=[tconst])

    if username:
        user_df = pd.read_sql_query(
            "SELECT id FROM users WHERE LOWER(name) = ?", conn, params=[username.lower()]
        )
        if not user_df.empty:
            user_id = user_df.iloc[0]['id']
            cursor = conn.cursor()
            cursor.execute(
                "SELECT movie_tconst, rating_label FROM ratings WHERE user_id = ?", (int(user_id),)
            )
            ratings_map = {row[0]: row[1] for row in cursor.fetchall()}
            df['rating_label'] = df['tconst'].map(ratings_map)

    conn.close()

    if df.empty:
        return []

    # Compute cosine similarities in one matrix operation
    embeddings = np.stack(df['plot_embedding'].apply(extract_embedding).values)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8
    similarities = (embeddings / norms) @ seed_norm

    top_idx = np.argsort(similarities)[::-1][:limit]
    result = df.iloc[top_idx].drop(columns=['plot_embedding'])
    return clean_data(result.to_dict(orient='records'))


@app.get("/predict/{username}/{tconst}")
def predict_score(username: str, tconst: str):
    model, metadata = load_user_model(username)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    m = get_movie_details(tconst)
    df = pd.DataFrame([{
        'year': m['year'],
        'genres': m['genres'],
        'runtime': m['runtime'],
        'imdb_rating': m['imdb_rating'],
        'num_votes': m.get('num_votes'),
        'directors': m['directors'],
        'writers': m['writers'],
        'actors': m['actors'],
        'plot': m['plot'],
        'composers': m.get('composers'),
        'certificates': m.get('certificates'),
        'languages': m.get('languages'),
        'countries': m.get('countries'),
        'keywords': m.get('keywords'),
        'plot_embedding': m.get('plot_embedding')
    }])
    
    X = metadata.prepare_features(df, use_cached_embeddings=True)
    score = model.predict(X)[0]
    score = max(0.0, min(10.0, float(score)))
    
    # Calculate SHAP explainability
    reasons = []
    try:
        # get_feature_importance with type='ShapValues' requires a catboost.Pool, not a raw DataFrame
        from catboost import Pool
        pool_X = Pool(X)
        shap_values = model.get_feature_importance(data=pool_X, type='ShapValues')
        
        # We only predict one instance at a time here
        instance_shaps = shap_values[0][:-1]  # Exclude the base value
        feature_names = model.feature_names_
        
        # Zip features with their SHAP contribution and sort by contribution descending
        feature_contributions = list(zip(feature_names, instance_shaps))
        feature_contributions.sort(key=lambda x: x[1], reverse=True)
        
        # Get top 5 positive contributors (must contribute > 0.1 to be worth mentioning)
        top_positive = [fc for fc in feature_contributions if fc[1] > 0.1][:10]  # Get more to filter
        
        for feature, contribution in top_positive:
            # Skip if we already have 5 reasons
            if len(reasons) >= 5:
                break
                
            # Translate raw feature names into human reasons
            if feature.startswith('genre_'):
                genre = feature.replace('genre_', '')
                reason = f"Genre: {genre}"
                if reason not in reasons:
                    reasons.append(reason)
                    
            elif feature.startswith('combo_'):
                # Genre combination: combo_Action_Sci-Fi -> "Action + Sci-Fi blend"
                parts = feature.replace('combo_', '').split('_')
                if len(parts) == 2:
                    reason = f"{parts[0]} + {parts[1]} blend"
                    if reason not in reasons:
                        reasons.append(reason)
                        
            elif feature == 'dir_avg_rating' and m.get('directors') and m.get('directors') != 'Unknown':
                known = metadata.person_ratings.get('directors', {})
                people = [p.strip() for p in m['directors'].split(',') if p.strip()]
                best = max((p for p in people if p in known), key=lambda p: known[p].get('avg', known[p]) if isinstance(known[p], dict) else known[p], default=None)
                if best:
                    reasons.append(f"Director: {best}")

            elif feature == 'wri_avg_rating' and m.get('writers') and m.get('writers') != 'Unknown':
                known = metadata.person_ratings.get('writers', {})
                people = [p.strip() for p in m['writers'].split(',') if p.strip()]
                best = max((p for p in people if p in known), key=lambda p: known[p].get('avg', known[p]) if isinstance(known[p], dict) else known[p], default=None)
                if best:
                    reasons.append(f"Writer: {best}")

            elif feature == 'act_avg_rating' and m.get('actors') and m.get('actors') != 'Unknown':
                known = metadata.person_ratings.get('actors', {})
                people = [p.strip() for p in m['actors'].split(',') if p.strip()]
                best = max((p for p in people if p in known), key=lambda p: known[p].get('avg', known[p]) if isinstance(known[p], dict) else known[p], default=None)
                if best:
                    reasons.append(f"Cast: {best}")

            elif feature == 'com_avg_rating' and m.get('composers') and m.get('composers') not in ['Unknown', None, '']:
                known = metadata.person_ratings.get('composers', {})
                people = [p.strip() for p in m['composers'].split(',') if p.strip()]
                best = max((p for p in people if p in known), key=lambda p: known[p].get('avg', known[p]) if isinstance(known[p], dict) else known[p], default=None)
                if best:
                    reasons.append(f"Score: {best}")
                
            elif feature.startswith('plot_emb_'):
                reason = "Plot matches your taste"
                if reason not in reasons:
                    reasons.append(reason)
                    
            elif feature == 'imdb_rating':
                reasons.append("Highly rated on IMDb")
                
            elif feature.startswith('kw_'):
                # Keyword tag: kw_time-travel -> "Tag: Time Travel"
                keyword = feature.replace('kw_', '').replace('-', ' ').title()
                reason = f"Tag: {keyword}"
                if reason not in reasons:
                    reasons.append(reason)
                    
            elif feature == 'year' and contribution > 0.1:
                year_val = int(df['year'].iloc[0]) if pd.notna(df['year'].iloc[0]) else None
                if year_val:
                    if year_val < 1980:
                        reasons.append("Golden age classic")
                    elif year_val < 1995:
                        reasons.append("From your favorite era")
                    else:
                        decade = (year_val // 10) * 10
                        reasons.append(f"From the {decade}s")
                        
            elif feature == 'decade' and contribution > 0.1:
                if 'year' in df.columns:
                    year_val = int(df['year'].iloc[0]) if pd.notna(df['year'].iloc[0]) else None
                    if year_val:
                        decade = (year_val // 10) * 10
                        reason = f"{decade}s film"
                        if reason not in reasons:
                            reasons.append(reason)
                    
            elif feature == 'is_classic' and contribution > 0.15:
                reason = "Classic era film"
                if reason not in reasons:
                    reasons.append(reason)
                
            elif feature == 'is_modern' and contribution > 0.15:
                reason = "Modern release"
                if reason not in reasons:
                    reasons.append(reason)
                
            elif feature == 'is_short' and contribution > 0.1:
                reasons.append("Perfect runtime")
                
            elif feature == 'is_long' and contribution > 0.1:
                reasons.append("Epic length you enjoy")
                
            elif feature == 'is_obscure' and contribution > 0.1:
                reasons.append("Hidden gem")
                
            elif feature == 'is_popular' and contribution > 0.1:
                reasons.append("Crowd favorite")
                
            elif feature == 'log_votes' and contribution > 0.1:
                votes = m.get('num_votes', 0)
                if votes and votes < 50000:
                    reasons.append("Under-the-radar pick")
                elif votes and votes > 500000:
                    reasons.append("Widely acclaimed")
                    
            elif feature.startswith('lang_') and contribution > 0.1:
                lang_map = {'english': 'English', 'spanish': 'Spanish', 'french': 'French', 'japanese': 'Japanese'}
                lang_code = feature.replace('lang_', '')
                lang_name = lang_map.get(lang_code, lang_code.title())
                reasons.append(f"{lang_name} cinema")
                
            elif feature.startswith('country_') and contribution > 0.1:
                country_map = {'usa': 'American', 'uk': 'British', 'spain': 'Spanish', 'france': 'French', 'japan': 'Japanese'}
                country_code = feature.replace('country_', '')
                country_name = country_map.get(country_code, country_code.upper())
                reasons.append(f"{country_name} film")
                
            elif feature.startswith('is_rated_') and contribution > 0.1:
                rating = feature.replace('is_rated_', '').replace('PG13', 'PG-13')
                reasons.append(f"{rating} rated")
                
        # Deduplicate and cap at 5 reasons
        reasons = list(dict.fromkeys(reasons))[:5]
            
    except Exception as e:
        logger.warning("Failed to calculate SHAP: %s", e)
        # Fail gracefully, explanations are optional
        pass
    
    return {
        "prediction": round(score, 1),
        "reasons": reasons
    }


FACTOR_TO_PERSON_KEY = {
    'cast': 'actors',
    'director': 'directors',
    'writer': 'writers',
    'composer': 'composers',
}


def get_liked_embeddings(user_id: int, conn):
    """Return stacked plot embeddings for movies this user rated >= 7."""
    liked_df = pd.read_sql_query(
        """SELECT m.plot_embedding FROM ratings r
           JOIN movies m ON r.movie_tconst = m.tconst
           WHERE r.user_id = ? AND r.rating_score >= 7 AND m.plot_embedding IS NOT NULL""",
        conn, params=[user_id]
    )
    if liked_df.empty:
        return None
    embeddings = [extract_embedding(b) for b in liked_df['plot_embedding'] if b is not None]
    return np.array(embeddings, dtype=np.float32) if embeddings else None


def compute_plot_factor_scores(df, liked_embeddings):
    """Cosine similarity of each candidate to the mean liked-movie embedding."""
    if liked_embeddings is None or len(liked_embeddings) == 0:
        return None
    taste_vector = liked_embeddings.mean(axis=0)
    norm = np.linalg.norm(taste_vector)
    if norm == 0:
        return None
    taste_vector = taste_vector / norm
    candidates = np.array([extract_embedding(b) for b in df['plot_embedding']], dtype=np.float32)
    norms = np.linalg.norm(candidates, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    candidates = candidates / norms
    return (candidates @ taste_vector).astype(float)


def compute_person_factor_scores(df, person_key, metadata):
    """Score each candidate by the highest known-person rating for the given field."""
    known = metadata.person_ratings.get(person_key, {})

    def best_known_score(people_str):
        if not people_str or pd.isna(people_str) or people_str == 'Unknown':
            return -1.0
        ratings = []
        for p in (p.strip() for p in people_str.split(',') if p.strip()):
            if p in known:
                val = known[p]
                ratings.append(val.get('avg', val) if isinstance(val, dict) else val)
        return max(ratings) if ratings else -1.0

    return np.array([best_known_score(row.get(person_key, '')) for _, row in df.iterrows()], dtype=float)


def sort_by_factor(df, factor, models_metadata, liked_embeddings_per_user, offset, limit):
    """Return the top slice of df sorted by factor, or None to fall back to default sort."""
    if factor in FACTOR_TO_PERSON_KEY:
        person_key = FACTOR_TO_PERSON_KEY[factor]
        # Average factor score across all users; ignore -1 (unknown) unless all are unknown
        all_scores = np.stack([
            compute_person_factor_scores(df, person_key, meta)
            for _, _, meta in models_metadata
        ])
        known_mask = all_scores > -1
        avg_scores = np.where(
            known_mask.any(axis=0),
            np.where(known_mask, all_scores, 0).sum(axis=0) / known_mask.sum(axis=0).clip(min=1),
            -1.0
        )
        df = df.copy()
        df['factor_score'] = avg_scores
        eligible = df[df['factor_score'] > -1]
        pool = eligible if len(eligible) > limit else df
        return pool.sort_values('predicted_score', ascending=False).iloc[offset:offset + limit]

    if factor == 'plot':
        # Average taste vectors across users, then cosine sim
        valid = [e for e in liked_embeddings_per_user if e is not None and len(e) > 0]
        if not valid:
            return None
        combined = np.concatenate(valid, axis=0)
        scores = compute_plot_factor_scores(df, combined)
        if scores is None:
            return None
        df = df.copy()
        df['factor_score'] = scores
        # Keep only the top half by plot similarity, then rank by predicted score
        threshold = np.median(df['factor_score'])
        pool = df[df['factor_score'] >= threshold]
        return pool.sort_values('predicted_score', ascending=False).iloc[offset:offset + limit]

    return None


@app.get("/recommendations/{username}", response_model=List[Movie])
def get_recommendations(username: str, genre: Optional[str] = None, factor: Optional[str] = None, offset: int = 0, limit: int = 24):
    model, metadata = load_user_model(username)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    conn = sqlite3.connect(DB_PATH)
    user_df = pd.read_sql_query("SELECT id FROM users WHERE LOWER(name) = ?", conn, params=[username.lower()])
    if user_df.empty:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user_df.iloc[0]['id']
    
    query = """
    SELECT tconst, title, year, genres, runtime, imdb_rating, num_votes, directors, writers, actors, plot, poster_url, plot_embedding,
           composers, certificates, languages, countries, keywords
    FROM movies
    WHERE tconst NOT IN (SELECT movie_tconst FROM ratings WHERE user_id = ?)
    """
    params = [int(user_id)]
    
    if genre:
        query += " AND genres LIKE ?"
        params.append(f"%{genre}%")
        
        
    query += " ORDER BY num_votes DESC LIMIT 1000"
    df = pd.read_sql_query(query, conn, params=params)
    liked_embeddings = get_liked_embeddings(int(user_id), conn) if factor == 'plot' else None
    conn.close()

    if df.empty:
        return []

    X = metadata.prepare_features(df, use_cached_embeddings=True)
    preds = model.predict(X)
    df['predicted_score'] = [round(max(0.0, min(10.0, float(p))), 1) for p in preds]

    top_movies = sort_by_factor(df, factor, [(username, model, metadata)], [liked_embeddings], offset, limit)
    if top_movies is None:
        top_movies = df.sort_values(by='predicted_score', ascending=False).iloc[offset:offset + limit]

    result_df = top_movies.drop(columns=['plot_embedding', 'factor_score'], errors='ignore')
    return clean_data(result_df.to_dict(orient="records"))


from fastapi import Query

@app.get("/recommend_shared", response_model=List[dict])
def get_shared_recommendations(users: List[str] = Query(...), factor: Optional[str] = None, offset: int = 0, limit: int = 12):
    """Get recommendations that work for multiple users based on the minimum predicted score."""
    if len(users) < 2:
        raise HTTPException(status_code=400, detail="Please provide at least two users for shared recommendations.")

    conn = sqlite3.connect(DB_PATH)

    user_ids = []
    models_metadata = []

    for username in users:
        model, metadata = load_user_model(username)
        if not model:
            conn.close()
            raise HTTPException(status_code=400, detail=f"User '{username}' does not have a trained model. They need to train their profile first.")

        user_df = pd.read_sql_query("SELECT id FROM users WHERE LOWER(name) = ?", conn, params=[username.lower()])
        if user_df.empty:
            conn.close()
            raise HTTPException(status_code=404, detail=f"User '{username}' not found.")

        user_ids.append(int(user_df.iloc[0]['id']))
        models_metadata.append((username, model, metadata))

    placeholders = ','.join(['?'] * len(user_ids))
    query = f"""
    SELECT tconst, title, year, genres, runtime, imdb_rating, num_votes, directors, writers, actors, plot, poster_url, plot_embedding,
           composers, certificates, languages, countries, keywords
    FROM movies
    WHERE tconst NOT IN (
          SELECT movie_tconst FROM ratings WHERE user_id IN ({placeholders})
      )
    ORDER BY num_votes DESC LIMIT 1000
    """

    try:
        df = pd.read_sql_query(query, conn, params=user_ids)
        liked_embeddings_per_user = (
            [get_liked_embeddings(uid, conn) for uid in user_ids] if factor == 'plot' else []
        )
    finally:
        conn.close()

    if df.empty:
        return []

    # Run predictions for each user
    score_columns = []
    for username, model, metadata in models_metadata:
        X = metadata.prepare_features(df, use_cached_embeddings=True)
        preds = model.predict(X)
        col_name = f"score_{username}"
        score_columns.append(col_name)
        df[col_name] = [max(0.0, min(10.0, float(p))) for p in preds]

    # Harmony Score = minimum across users; avg as tiebreaker
    df['predicted_score'] = df[score_columns].min(axis=1).round(1)
    df['avg_score'] = df[score_columns].mean(axis=1)
    for col in score_columns:
        df[col] = df[col].round(1)

    top_movies = sort_by_factor(df, factor, models_metadata, liked_embeddings_per_user, offset, limit)
    if top_movies is None:
        top_movies = df.sort_values(by=['predicted_score', 'avg_score'], ascending=[False, False]).iloc[offset:offset + limit]

    results = []
    for _, row in top_movies.iterrows():
        movie_dict = row.drop(labels=['plot_embedding', 'avg_score', 'factor_score'] + score_columns, errors='ignore').to_dict()
        individual_scores = {u: row[f"score_{u}"] for u in users}
        movie_dict["individual_scores"] = individual_scores
        results.append(movie_dict)
        
    return clean_data(results)


@app.post("/rate")
def rate_movie(username: str, tconst: str, score: float, label: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get/Create user
    cursor.execute("SELECT id FROM users WHERE LOWER(name) = ?", (username.lower(),))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (name) VALUES (?)", (username,))
        user_id = cursor.lastrowid
    else:
        user_id = row[0]
        
    # Check if movie exists, if not fetch and save
    cursor.execute("SELECT tconst FROM movies WHERE tconst = ?", (tconst,))
    if not cursor.fetchone():
        get_movie_details(tconst)  # This saves to DB
        
    # Save rating
    cursor.execute("""
        INSERT OR REPLACE INTO ratings (user_id, movie_tconst, rating_label, rating_score)
        VALUES (?, ?, ?, ?)
    """, (user_id, tconst, label, score))
    
    conn.commit()
    conn.close()
    return {"status": "success"}


@app.post("/retrain/{username}")
def retrain_model(username: str):
    """Trigger model retraining for a user and return insights."""
    from train_model import train
    
    try:
        insights = train(username, verbose=True)
        # Clear cache to reload new model
        cache_key = username.lower()
        if cache_key in _model_cache:
            del _model_cache[cache_key]
        
        if insights is None:
            raise HTTPException(status_code=400, detail="Not enough ratings to train model (minimum 10)")
        
        return {
            "status": "success", 
            "message": f"Model retrained for {username}",
            "insights": insights
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/insights/{username}")
def get_insights(username: str):
    """Get saved insights for a user's model."""
    import json
    from train_model import analyze_maturity_preference

    insights_path = os.path.join(DATA_DIR, f'model_{username}_insights.json')

    if not os.path.exists(insights_path):
        raise HTTPException(status_code=404, detail="No insights found. Train your model first.")

    with open(insights_path, 'r', encoding='utf-8') as f:
        insights = json.load(f)

    # Recompute maturity_preference live if the saved data is stale (empty ratings)
    if not insights.get('maturity_preference', {}).get('ratings'):
        conn = sqlite3.connect(DB_PATH)
        try:
            user_df = pd.read_sql_query(
                "SELECT id FROM users WHERE LOWER(name) = ?", conn, params=[username.lower()]
            )
            if not user_df.empty:
                user_id = int(user_df.iloc[0]['id'])
                rated_df = pd.read_sql_query(
                    """SELECT r.rating_score, m.certificates
                       FROM ratings r JOIN movies m ON r.movie_tconst = m.tconst
                       WHERE r.user_id = ?""",
                    conn, params=[user_id]
                )
                insights['maturity_preference'] = analyze_maturity_preference(rated_df)
        finally:
            conn.close()

    return clean_data(insights)


@app.post("/users")
def create_user(name: str):
    """Create a new user profile."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if user already exists
    cursor.execute("SELECT id FROM users WHERE LOWER(name) = ?", (name.lower(),))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="User already exists")
    
    cursor.execute("INSERT INTO users (name) VALUES (?)", (name,))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {"id": user_id, "name": name}


@app.get("/stats/{username}")
def get_user_stats(username: str):
    """Get rating statistics for a user."""
    conn = sqlite3.connect(DB_PATH)
    
    # Get user id
    user_df = pd.read_sql_query("SELECT id FROM users WHERE LOWER(name) = ?", conn, params=[username.lower()])
    if user_df.empty:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user_df.iloc[0]['id']
    
    # Get all ratings with movie info
    ratings_df = pd.read_sql_query("""
        SELECT r.rating_score, r.rating_label, r.timestamp,
               m.title, m.year, m.genres, m.runtime, m.imdb_rating, m.poster_url, m.tconst
        FROM ratings r
        JOIN movies m ON r.movie_tconst = m.tconst
        WHERE r.user_id = ?
        ORDER BY r.timestamp DESC
    """, conn, params=[int(user_id)])
    conn.close()
    
    if ratings_df.empty:
        return {
            "total_ratings": 0,
            "average_score": 0,
            "genre_stats": [],
            "decade_stats": [],
            "recent_ratings": [],
            "score_distribution": [],
            "has_model": False
        }
    
    # Basic stats
    total_ratings = len(ratings_df)
    average_score = round(ratings_df['rating_score'].mean(), 1)
    
    # Genre stats
    genre_scores = {}
    genre_counts = {}
    for _, row in ratings_df.iterrows():
        if row['genres']:
            for genre in str(row['genres']).split(','):
                genre = genre.strip()
                if genre:
                    genre_scores[genre] = genre_scores.get(genre, 0) + row['rating_score']
                    genre_counts[genre] = genre_counts.get(genre, 0) + 1
    
    genre_stats = [
        {"genre": g, "avg_score": round(genre_scores[g] / genre_counts[g], 1), "count": genre_counts[g]}
        for g in genre_counts if genre_counts[g] >= 2
    ]
    genre_stats.sort(key=lambda x: x['avg_score'], reverse=True)
    
    # Decade stats - drop movies with no year to avoid NaN decades
    temp_df = ratings_df.dropna(subset=['year']).copy()
    if not temp_df.empty:
        temp_df['decade'] = (temp_df['year'].astype(int) // 10) * 10
        decade_groups = temp_df.groupby('decade').agg({
            'rating_score': ['mean', 'count']
        }).reset_index()
        decade_groups.columns = ['decade', 'avg_score', 'count']
        decade_stats = [
            {"decade": f"{int(row['decade'])}s", "avg_score": round(row['avg_score'], 1), "count": int(row['count'])}
            for _, row in decade_groups.iterrows()
        ]
    else:
        decade_stats = []
    
    # Recent ratings (last 10)
    recent_ratings = ratings_df.head(10).to_dict(orient='records')
    
    # Score distribution
    score_bins = [0, 2, 4, 6, 8, 10]
    score_labels = ['0-2', '2-4', '4-6', '6-8', '8-10']
    ratings_df['score_bin'] = pd.cut(ratings_df['rating_score'], bins=score_bins, labels=score_labels, include_lowest=True)
    distribution = ratings_df['score_bin'].value_counts().to_dict()
    score_distribution = [{"range": label, "count": distribution.get(label, 0)} for label in score_labels]
    
    # Check if model exists
    model_path = os.path.join(DATA_DIR, f'model_{username}.cbm')
    has_model = os.path.exists(model_path)
    
    return clean_data({
        "total_ratings": total_ratings,
        "average_score": average_score,
        "genre_stats": genre_stats[:10],  # Top 10 genres
        "decade_stats": decade_stats,
        "recent_ratings": recent_ratings,
        "score_distribution": score_distribution,
        "has_model": has_model
    })


@app.get("/genres")
def get_genres():
    """Get list of all available genres."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT genres FROM movies WHERE genres IS NOT NULL LIMIT 1000")
    rows = cursor.fetchall()
    conn.close()
    
    all_genres = set()
    for row in rows:
        if row[0]:
            for genre in row[0].split(','):
                all_genres.add(genre.strip())
    
    return clean_data(sorted(list(all_genres)))


@app.delete("/ratings/{username}/{tconst}")
def delete_rating(username: str, tconst: str):
    """Delete a rating for a movie."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get user id
    cursor.execute("SELECT id FROM users WHERE LOWER(name) = ?", (username.lower(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = row[0]
    
    cursor.execute("DELETE FROM ratings WHERE user_id = ? AND movie_tconst = ?", (user_id, tconst))
    conn.commit()
    conn.close()
    
    return {"status": "success"}


@app.get("/random/{username}", response_model=List[Movie])
def get_random_movies(
    username: str, 
    year: Optional[int] = None, 
    genre: Optional[str] = None,
    limit: int = 20
):
    """Get random popular unrated movies for a user to rate."""
    import random as rand
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get user id
    user_df = pd.read_sql_query("SELECT id FROM users WHERE LOWER(name) = ?", conn, params=[username.lower()])
    if user_df.empty:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user_df.iloc[0]['id']
    
    # Build query for unrated movies, ordered by popularity
    query = """
        SELECT tconst, title, year, genres, runtime, imdb_rating, directors, actors, plot, poster_url
        FROM movies 
        WHERE tconst NOT IN (SELECT movie_tconst FROM ratings WHERE user_id = ?)
          AND title IS NOT NULL
          AND imdb_rating IS NOT NULL
    """
    params = [int(user_id)]
    
    if year:
        query += " AND year = ?"
        params.append(year)
    if genre:
        query += " AND genres LIKE ?"
        params.append(f"%{genre}%")
    
    query += " ORDER BY RANDOM() LIMIT 1000"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        return []

    # Weighted sample: prefer movies with both poster and plot for a better
    # rating experience, but don't hard-exclude movies that lack them.
    has_content = df['poster_url'].notna() & df['plot'].notna()
    weights = has_content.map({True: 3, False: 1})
    sampled = df.sample(n=min(limit, len(df)), weights=weights)

    return clean_data(sampled.to_dict(orient="records"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
