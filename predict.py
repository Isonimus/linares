"""
Inference script for LINARES movie predictor.

Uses the improved feature engineering pipeline with:
- Pre-computed embeddings from database
- Target-encoded person features
- Multi-hot genre encoding
"""

import pandas as pd
import config
import logging
import warnings
# Suppress transformers and huggingface warnings
logging.getLogger("transformers").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")
from catboost import CatBoostRegressor
import sqlite3
import os
import textwrap
from db import DB_PATH, DATA_DIR
from imdb_utils import search_imdb_movies, get_movie_details
from features import FeatureMetadata


def load_user_model(username):
    """Load trained model and metadata for a user."""
    model_path = os.path.join(DATA_DIR, f'model_{username}.cbm')
    metadata_path = os.path.join(DATA_DIR, f'model_{username}_metadata.json')
    
    if not os.path.exists(model_path):
        print(f"❌ No trained model found for '{username}'.")
        print(f"Please run 'python train_model.py' first.")
        return None, None
        
    model = CatBoostRegressor()
    model.load_model(model_path)
    
    # Load metadata for feature engineering
    metadata = FeatureMetadata.load(metadata_path)
    
    return model, metadata


def predict_single_movie(username, title_search):
    """Fetches a movie from IMDb API, format it and predict the rating."""
    model, metadata = load_user_model(username)
    if not model:
        return
    
    print(f"\n🔍 Searching '{title_search}' on IMDb...")
    movies = search_imdb_movies(title_search)

    if not movies:
        print("No results found.")
        return

    print("\nResults found:")
    top_picks = movies[:5]
    for i, m in enumerate(top_picks):
        year = m.get('y', '????')
        title = m.get('l', 'Unknown')
        tipo = m.get('q', 'Unknown')
        print(f"[{i + 1}] {title} ({year}) - {tipo}")

    print("[0] Cancel search")

    while True:
        try:
            choice = int(input("\nChoose an option (0-5): ").strip())
            if choice == 0:
                return
            if 1 <= choice <= len(top_picks):
                selected_movie_id = top_picks[choice - 1].get('id')
                break
            else:
                print("Option out of range.")
        except ValueError:
            print("Please enter a valid number.")
            
    # Fetch details via central utility (handles DB caching)
    m = get_movie_details(selected_movie_id)
    
    print(f"\n🎥 Found: {m['title']} ({m['year']}) [{m['source']}]")
    print(f"🎭 {m['genres']} | ⏱️ {m['runtime']} min | ⭐ IMDb: {m['imdb_rating']}/10")
    print(f"🎬 Dir: {m['directors']}")
    print(f"🤝 Cast: {m['actors']}")
    
    # Create DataFrame with all columns needed by the model
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
        'plot_embedding': m.get('plot_embedding')  # May be None if live fetched
    }])
    
    # Prepare features using metadata (for consistent person encoding)
    X = metadata.prepare_features(df, use_cached_embeddings=True)
    
    # Predict
    pred_score = model.predict(X)[0]
    
    # Clip to 0-10 just in case
    pred_score = max(0.0, min(10.0, pred_score))
    
    print("\n" + "="*50)
    print(f"🤖 PREDICTION FOR {username.upper()}: {pred_score:.1f} / 10")
    print("="*50 + "\n")
    

def recommend_movies(username, filter_genre=None, limit=5):
    """Recommends N movies from the local DB that the user hasn't rated yet."""
    model, metadata = load_user_model(username)
    if not model:
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get user id
    user_df = pd.read_sql_query("SELECT id FROM users WHERE LOWER(name) = ?", conn, params=(username.lower(),))
    if user_df.empty:
        print(f"User '{username}' not found.")
        conn.close()
        return
    user_id = user_df.iloc[0]['id']
    
    # Query all popular unseen movies with plots and embeddings
    query = """
    SELECT tconst, title, year, genres, runtime, imdb_rating, num_votes, directors, writers, actors, plot, plot_embedding,
           composers, certificates, languages, countries, keywords
    FROM movies
    WHERE plot IS NOT NULL AND plot != ''
      AND tconst NOT IN (SELECT movie_tconst FROM ratings WHERE user_id = ?)
    """
    params = [int(user_id)]
    
    if filter_genre:
        query += " AND genres LIKE ?"
        params.append(f"%{filter_genre}%")
        
    # We take the top 500 by global popularity to feed to the network
    query += " ORDER BY num_votes DESC LIMIT 500"
    
    print(f"\n🧠 Analysing candidate movies. Please wait...")
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        print("Not enough movies with plot summaries to analyse.")
        print("Make sure to run 'python fetch_metadata.py' to populate the database.")
        return

    # Count cached embeddings
    cached_count = df['plot_embedding'].notna().sum()
    print(f"✅ Candidate pool ready: {len(df)} movies ({cached_count} with pre-computed embeddings)")
    
    if cached_count < len(df):
        print(f"⚠️ Calculando {len(df) - cached_count} embeddings faltantes...")
    
    if len(df) < 200:
        print("⚠️ Note: The candidate pool is small. Run 'fetch_metadata.py' for longer to get better results.")
    
    # Prepare features using metadata
    X = metadata.prepare_features(df, use_cached_embeddings=True)
    
    # Predict scores for all candidates
    preds = model.predict(X)
    df['predicted_score'] = [max(0.0, min(10.0, float(p))) for p in preds]
    
    # Sort by predicted score
    top_movies = df.sort_values(by='predicted_score', ascending=False).head(limit)
    
    print("\n" + "="*60)
    print(f"🍿 TOP {limit} RECOMMENDATIONS FOR {username.upper()} 🍿")
    print("="*60 + "\n")
    
    for idx, row in top_movies.iterrows():
        print(f"[{row['predicted_score']:.1f}/10] 🎥 {row['title']} ({row['year']})")
        print(f"        🎭 {row['genres']} | ⭐ IMDb Global: {row['imdb_rating']}/10")
        print(f"        🎬 Dir: {row['directors']}")
        print(f"        🤝 Cast: {row['actors']}")
        print("        " + "-"*50)
        wrapped_plot = textwrap.fill(str(row['plot']), width=70, initial_indent="        ", subsequent_indent="        ")
        print(wrapped_plot)
        print("\n")


if __name__ == '__main__':
    print("\n🔮 LINARES Movie Predictor 🔮")
    username = input("Your profile name: ").strip()

    if username:
        print("\nWhat would you like to do?")
        print("1. Predict my score for a specific movie")
        print("2. Get AI movie recommendations")

        choice = input("Option (1/2): ").strip()

        if choice == '1':
            movie_name = input("Movie title to search: ").strip()
            predict_single_movie(username, movie_name)
        elif choice == '2':
            genre = input("Optional genre filter (e.g. Sci-Fi, Action). Press Enter to skip: ").strip()
            limit_str = input("Number of recommendations (default 5): ").strip()
            limit = int(limit_str) if limit_str.isdigit() else 5
            recommend_movies(username, filter_genre=genre, limit=limit)
        else:
            print("Invalid option.")
