"""
Feature engineering module for LINARES movie predictor.

This module provides consistent feature transformation for both training and inference.
All feature engineering logic is centralized here to ensure consistency.
"""

import numpy as np
import pandas as pd
import json
import os
from datetime import datetime
from sentence_transformers import SentenceTransformer

# Known genres from IMDb (most common)
KNOWN_GENRES = [
    'Action', 'Adventure', 'Animation', 'Biography', 'Comedy', 'Crime',
    'Documentary', 'Drama', 'Family', 'Fantasy', 'Film-Noir', 'History',
    'Horror', 'Music', 'Musical', 'Mystery', 'Romance', 'Sci-Fi',
    'Sport', 'Thriller', 'War', 'Western'
]

# Meaningful genre combinations that capture distinct film types
# These pairs represent recognizable sub-genres or hybrid styles
GENRE_COMBINATIONS = [
    # Sci-Fi hybrids
    ('Action', 'Sci-Fi'),       # Blockbuster sci-fi (Terminator, Matrix)
    ('Drama', 'Sci-Fi'),        # Thoughtful sci-fi (Arrival, Interstellar)
    ('Horror', 'Sci-Fi'),       # Sci-fi horror (Alien, Event Horizon)
    ('Thriller', 'Sci-Fi'),     # Sci-fi thriller (Ex Machina)
    
    # Action hybrids
    ('Action', 'Comedy'),       # Action comedy (Rush Hour, Bad Boys)
    ('Action', 'Crime'),        # Crime action (Heat, John Wick)
    ('Action', 'Adventure'),    # Adventure action (Indiana Jones, Pirates)
    ('Action', 'Thriller'),     # Action thriller (Die Hard, Bourne)
    
    # Drama hybrids
    ('Drama', 'Mystery'),       # Mystery drama (Zodiac, Prisoners)
    ('Drama', 'Thriller'),      # Thriller drama (Se7en, Gone Girl)
    ('Drama', 'Romance'),       # Romantic drama (Titanic, Notebook)
    ('Drama', 'Crime'),         # Crime drama (Godfather, Goodfellas)
    ('Drama', 'War'),           # War drama (Saving Private Ryan)
    ('Drama', 'Biography'),     # Biopic (Schindler's List)
    
    # Horror hybrids
    ('Horror', 'Thriller'),     # Horror thriller (Get Out, Silence of Lambs)
    ('Horror', 'Mystery'),      # Horror mystery (The Ring, Sinister)
    ('Horror', 'Comedy'),       # Horror comedy (Shaun of Dead, Scream)
    
    # Comedy hybrids
    ('Comedy', 'Romance'),      # Romantic comedy (When Harry Met Sally)
    ('Comedy', 'Drama'),        # Dramedy (Little Miss Sunshine)
    ('Comedy', 'Adventure'),    # Adventure comedy (Jumanji)
    
    # Fantasy hybrids
    ('Adventure', 'Fantasy'),   # Fantasy adventure (LOTR, Harry Potter)
    ('Drama', 'Fantasy'),       # Fantasy drama (Pan's Labyrinth)
    ('Action', 'Fantasy'),      # Fantasy action (300, Thor)
    
    # Other notable combos
    ('Mystery', 'Thriller'),    # Mystery thriller (Shutter Island)
    ('Animation', 'Adventure'), # Animated adventure (Pixar, Ghibli)
    ('Animation', 'Comedy'),    # Animated comedy (Shrek)
    ('Animation', 'Drama'),     # Animated drama (Grave of Fireflies)
]

# Embedding dimension for all-MiniLM-L6-v2
EMBEDDING_DIM = 384

# Fallback keywords for users with very few ratings (used when dynamic selection not possible)
# These are high-signal thematic tags that tend to be predictive across many users
FALLBACK_KEYWORDS = [
    'based-on-novel', 'based-on-true-story', 'independent-film',
    'revenge', 'murder', 'friendship', 'redemption', 'love',
    'dystopia', 'time-travel', 'artificial-intelligence', 'cyberpunk',
    'heist', 'survival', 'coming-of-age', 'betrayal', 'conspiracy',
    'post-apocalypse', 'superhero', 'martial-arts', 'space',
    'psychological-thriller', 'serial-killer', 'haunted-house',
    'zombie', 'vampire', 'alien', 'robot', 'monster',
    'world-war-two', 'vietnam-war', 'cold-war',
    'based-on-comic', 'sequel', 'remake', 'flashback',
    'nonlinear-timeline', 'twist-ending', 'plot-twist',
]

# Keywords to always exclude (too generic or noisy)
KEYWORD_BLACKLIST = {
    'male-protagonist', 'female-protagonist', 'title-spoken-by-character',
    'reference-to', 'character-name-in-title', 'surprise-ending',
    'photograph', 'scene-during-opening-credits', 'scene-after-end-credits',
    'post-credits-scene', 'mid-credits-scene', 'opening-action-scene',
    'no-opening-credits', 'f-word', 'held-at-gunpoint', 'shot-in-the-head',
    'shot-to-death', 'blood', 'gore', 'violence', 'death', 'fire',
    'explosion', 'fight', 'chase', 'escape', 'kiss', 'love',  # too common
}


def extract_dynamic_keywords(rated_df, min_count=2, max_keywords=100):
    """
    Extract the most relevant keywords from user's rated movies.
    
    The number of keywords scales with the amount of training data:
    - Fewer ratings → fewer keywords (avoid overfitting)
    - More ratings → more keywords (capture more nuance)
    
    Args:
        rated_df: DataFrame with 'keywords' column
        min_count: Minimum appearances for a keyword to be included
        max_keywords: Maximum number of keywords to select
        
    Returns:
        list: Selected keywords sorted by frequency
    """
    from collections import Counter
    
    if 'keywords' not in rated_df.columns:
        return FALLBACK_KEYWORDS[:30]
    
    # Count all keywords
    keyword_counts = Counter()
    for kw_str in rated_df['keywords'].dropna():
        if not kw_str or kw_str == 'None':
            continue
        keywords = [k.strip().lower() for k in str(kw_str).split(',') if k.strip()]
        for kw in keywords:
            if kw and kw not in KEYWORD_BLACKLIST:
                keyword_counts[kw] += 1
    
    # Filter by minimum count
    valid_keywords = [(kw, count) for kw, count in keyword_counts.items() if count >= min_count]
    
    if len(valid_keywords) < 10:
        # Not enough data, use fallback
        return FALLBACK_KEYWORDS[:30]
    
    # Adaptive count: ~1 keyword per 3 rated movies, capped at max_keywords
    # This prevents overfitting with few ratings while allowing detail with many
    num_ratings = len(rated_df)
    target_keywords = min(max_keywords, max(20, num_ratings // 3))
    
    # Sort by frequency and take top N
    valid_keywords.sort(key=lambda x: x[1], reverse=True)
    selected = [kw for kw, _ in valid_keywords[:target_keywords]]
    
    return selected

# Cache for embedder
_embedder_cache = None


def get_embedder():
    """Get or create the sentence transformer embedder."""
    global _embedder_cache
    if _embedder_cache is None:
        _embedder_cache = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedder_cache


def multi_hot_encode_genres(genres_str):
    """
    Convert a comma-separated genre string to multi-hot encoding.
    
    Args:
        genres_str: String like "Action,Sci-Fi,Thriller"
        
    Returns:
        Dict with genre_X: 0 or 1 for each known genre
    """
    if not genres_str or pd.isna(genres_str):
        genres_list = []
    else:
        genres_list = [g.strip() for g in str(genres_str).split(',')]
    
    return {f'genre_{g}': (1 if g in genres_list else 0) for g in KNOWN_GENRES}


def encode_genre_combinations(genres_str):
    """
    Encode meaningful genre pair combinations.
    
    This captures hybrid sub-genres that behave differently from their parts:
    - "Action + Comedy" is a different experience than Action OR Comedy alone
    - "Drama + Sci-Fi" represents thoughtful sci-fi vs pure action sci-fi
    
    Args:
        genres_str: String like "Action,Sci-Fi,Thriller"
        
    Returns:
        Dict with combo_X_Y: 0 or 1 for each defined genre combination
    """
    if not genres_str or pd.isna(genres_str):
        genres_set = set()
    else:
        genres_set = {g.strip() for g in str(genres_str).split(',')}
    
    result = {}
    for g1, g2 in GENRE_COMBINATIONS:
        # Alphabetical ordering for consistent naming
        name = f'combo_{min(g1,g2)}_{max(g1,g2)}'
        result[name] = 1 if (g1 in genres_set and g2 in genres_set) else 0
    
    return result


def compute_person_features(df, column_name, rated_df=None, min_appearances=2):
    """
    Compute target-encoded features for people (directors, writers, actors).
    
    Instead of treating each unique combination as a category, we:
    1. Calculate average rating per person from training data
    2. Use mean/max/min of those averages for each movie
    
    Args:
        df: DataFrame with the column to process
        column_name: Name of the column ('directors', 'writers', 'actors')
        rated_df: DataFrame with rated movies (contains 'rating_score' and the column)
                  If None, returns just count features
        min_appearances: Minimum appearances to use person's average (otherwise use global mean)
    
    Returns:
        DataFrame with new features
    """
    prefix = column_name[:3]  # 'dir', 'wri', 'act'
    
    # Build person -> average rating mapping from training data
    person_ratings = {}
    global_mean = 5.0  # Default
    
    if rated_df is not None and 'rating_score' in rated_df.columns:
        global_mean = rated_df['rating_score'].mean()
        
        # Count appearances and sum ratings per person
        person_sum = {}
        person_count = {}
        
        for _, row in rated_df.iterrows():
            people_str = row.get(column_name, '')
            if not people_str or pd.isna(people_str):
                continue
            people = [p.strip() for p in str(people_str).split(',') if p.strip() and p.strip() != 'Unknown']
            score = row['rating_score']
            
            for person in people:
                person_sum[person] = person_sum.get(person, 0) + score
                person_count[person] = person_count.get(person, 0) + 1
        
        # Calculate averages (with minimum appearance threshold)
        for person, count in person_count.items():
            if count >= min_appearances:
                person_ratings[person] = person_sum[person] / count
    
    # Now compute features for each row
    features = []
    for _, row in df.iterrows():
        people_str = row.get(column_name, '')
        if not people_str or pd.isna(people_str):
            people = []
        else:
            people = [p.strip() for p in str(people_str).split(',') if p.strip() and p.strip() != 'Unknown']
        
        if not people:
            features.append({
                f'{prefix}_count': 0,
                f'{prefix}_avg_rating': global_mean,
                f'{prefix}_max_rating': global_mean,
                f'{prefix}_min_rating': global_mean,
                f'{prefix}_known_count': 0,
            })
        else:
            ratings = [person_ratings.get(p, global_mean) for p in people]
            known_count = sum(1 for p in people if p in person_ratings)

            features.append({
                f'{prefix}_count': len(people),
                f'{prefix}_avg_rating': np.mean(ratings),
                f'{prefix}_max_rating': np.max(ratings),
                f'{prefix}_min_rating': np.min(ratings),
                f'{prefix}_known_count': known_count,
            })
    
    return pd.DataFrame(features, index=df.index)


def extract_certificate_mppa(cert_str):
    """Extract standard US rating from IMDb certificate string."""
    if not cert_str or pd.isna(cert_str):
        return 'Unknown'
    certs = [c.strip() for c in str(cert_str).split(',')]
    for c in certs:
        if c.startswith('USA:'):
            val = c.replace('USA:', '')
            if val in ['G', 'PG', 'PG-13', 'R', 'NC-17']:
                return val
    return 'Unknown'


def multi_hot_encode_top_categories(series, prefix, known_values):
    """Helper to multi-hot encode list-like categories."""
    def encode_row(val):
        if not val or pd.isna(val):
            items = []
        else:
            items = [i.strip() for i in str(val).split(',')]
        return {f'{prefix}_{i}': (1 if i in items else 0) for i in known_values}
    
    return series.apply(encode_row).apply(pd.Series)


def _multi_hot_keywords(kw_str, keyword_list):
    """Convert a comma-separated keywords string to multi-hot dict.
    
    Args:
        kw_str: Comma-separated keywords string from the movie
        keyword_list: List of keywords to encode (dynamic per user)
    """
    if not kw_str or (isinstance(kw_str, float) and pd.isna(kw_str)):
        items = set()
    else:
        items = {k.strip().lower() for k in str(kw_str).split(',') if k.strip()}
    return {f'kw_{kw}': (1 if kw in items else 0) for kw in keyword_list}

def extract_embedding(embedding_blob):
    """Convert a BLOB to numpy array."""
    if embedding_blob is None:
        return np.zeros(EMBEDDING_DIM, dtype=np.float32)
    return np.frombuffer(embedding_blob, dtype=np.float32)


def compute_embeddings(plots, cached_embeddings=None):
    """
    Get embeddings for plots, using cache when available.
    
    Args:
        plots: List of plot strings
        cached_embeddings: List of cached embedding blobs (can contain None)
        
    Returns:
        numpy array of shape (len(plots), EMBEDDING_DIM)
    """
    if cached_embeddings is None:
        cached_embeddings = [None] * len(plots)
    
    result = np.zeros((len(plots), EMBEDDING_DIM), dtype=np.float32)
    to_compute_indices = []
    to_compute_plots = []
    
    for i, (plot, cached) in enumerate(zip(plots, cached_embeddings)):
        if cached is not None:
            result[i] = extract_embedding(cached)
        else:
            to_compute_indices.append(i)
            to_compute_plots.append(plot if plot else "")
    
    # Compute missing embeddings
    if to_compute_plots:
        embedder = get_embedder()
        computed = embedder.encode(to_compute_plots, show_progress_bar=False)
        for idx, embedding in zip(to_compute_indices, computed):
            result[idx] = embedding
    
    return result


class FeatureMetadata:
    """Stores metadata needed for consistent feature engineering at inference time."""
    
    def __init__(self):
        self.person_ratings = {
            'directors': {},
            'writers': {},
            'actors': {},
            'composers': {}
        }
        self.studio_ratings = {}
        self.global_mean = 5.0
        self.selected_keywords = []  # Dynamic keywords selected during training
    
    def fit(self, rated_df):
        """Learn person ratings and extract dynamic keywords from training data."""
        if 'rating_score' not in rated_df.columns:
            return
        
        self.global_mean = rated_df['rating_score'].mean()
        
        # Extract dynamic keywords based on user's rated movies
        self.selected_keywords = extract_dynamic_keywords(rated_df)
        
        for col in ['directors', 'writers', 'actors', 'composers']:
            if col not in rated_df.columns:
                continue

            person_sum = {}
            person_count = {}

            for _, row in rated_df.iterrows():
                people_str = row.get(col, '')
                if not people_str or pd.isna(people_str):
                    continue
                people = [p.strip() for p in str(people_str).split(',') if p.strip() and p.strip() != 'Unknown']
                score = row['rating_score']

                for person in people:
                    person_sum[person] = person_sum.get(person, 0) + score
                    person_count[person] = person_count.get(person, 0) + 1

            # Calculate averages (min 2 appearances) - store both avg and count
            for person, count in person_count.items():
                if count >= 2:
                    self.person_ratings[col][person] = {
                        'avg': person_sum[person] / count,
                        'count': count
                    }

        # Studio target encoding
        if 'studios' in rated_df.columns:
            studio_sum = {}
            studio_count = {}
            for _, row in rated_df.iterrows():
                studios_str = row.get('studios', '')
                if not studios_str or pd.isna(studios_str):
                    continue
                studios = [s.strip() for s in str(studios_str).split(',') if s.strip()]
                score = row['rating_score']
                for studio in studios:
                    studio_sum[studio] = studio_sum.get(studio, 0) + score
                    studio_count[studio] = studio_count.get(studio, 0) + 1
            for studio, count in studio_count.items():
                if count >= 2:
                    self.studio_ratings[studio] = studio_sum[studio] / count
    
    def save(self, filepath):
        """Save metadata to JSON file."""
        data = {
            'person_ratings': self.person_ratings,
            'studio_ratings': self.studio_ratings,
            'global_mean': self.global_mean,
            'selected_keywords': self.selected_keywords
        }
        with open(filepath, 'w') as f:
            json.dump(data, f)

    @classmethod
    def load(cls, filepath):
        """Load metadata from JSON file."""
        metadata = cls()
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                metadata.person_ratings = data.get('person_ratings', metadata.person_ratings)
                metadata.studio_ratings = data.get('studio_ratings', {})
                metadata.global_mean = data.get('global_mean', 5.0)
                metadata.selected_keywords = data.get('selected_keywords', FALLBACK_KEYWORDS[:30])
        return metadata
    
    def prepare_features(self, df, use_cached_embeddings=True):
        """Prepare features using stored metadata (for inference)."""
        features = pd.DataFrame(index=df.index)
        
        # 1. Numeric features
        year_series = pd.to_numeric(df['year'], errors='coerce')
        features['year'] = year_series.fillna(2000).astype(int)
        
        runtime_series = pd.to_numeric(df['runtime'], errors='coerce')
        features['runtime'] = runtime_series.fillna(100).astype(int)
        
        imdb_col = df['imdb_rating'] if 'imdb_rating' in df.columns else pd.Series([6.0] * len(df), index=df.index)
        imdb_series = pd.to_numeric(imdb_col, errors='coerce')
        features['imdb_rating'] = imdb_series.fillna(6.0)
        
        # Popularity (num_votes) - log-scaled since it varies from hundreds to millions
        if 'num_votes' in df.columns:
            votes_series = pd.to_numeric(df['num_votes'], errors='coerce').fillna(1000)
            features['log_votes'] = np.log10(votes_series.clip(lower=1))
            features['is_popular'] = (votes_series > 100000).astype(int)
            features['is_obscure'] = (votes_series < 10000).astype(int)
        
        # 2. Derived temporal features
        features['decade'] = (features['year'] // 10) * 10
        features['years_since_release'] = datetime.now().year - features['year']
        features['is_classic'] = (features['year'] < 1980).astype(int)
        features['is_modern'] = (features['year'] >= 2010).astype(int)
        
        # 3. Runtime categories
        features['is_short'] = (features['runtime'] < 90).astype(int)
        features['is_long'] = (features['runtime'] > 150).astype(int)
        
        # 4. Multi-hot encoded genres
        genre_features = df['genres'].apply(multi_hot_encode_genres).apply(pd.Series)
        features = pd.concat([features, genre_features], axis=1)
        
        # 4b. Genre combinations (hybrid sub-genres)
        combo_features = df['genres'].apply(encode_genre_combinations).apply(pd.Series)
        features = pd.concat([features, combo_features], axis=1)
        
        # 5. Person-like features using stored ratings
        for col in ['directors', 'writers', 'actors', 'composers']:
            prefix = col[:3]
            person_ratings = self.person_ratings.get(col, {})
            
            person_features = []
            for _, row in df.iterrows():
                people_str = row.get(col, '')
                if not people_str or pd.isna(people_str):
                    people = []
                else:
                    people = [p.strip() for p in str(people_str).split(',') if p.strip() and p.strip() != 'Unknown']
                
                if not people:
                    person_features.append({
                        f'{prefix}_count': 0,
                        f'{prefix}_avg_rating': self.global_mean,
                        f'{prefix}_max_rating': self.global_mean,
                        f'{prefix}_min_rating': self.global_mean,
                        f'{prefix}_known_count': 0,
                    })
                else:
                    ratings = [person_ratings.get(p, {'avg': self.global_mean}).get('avg', self.global_mean) for p in people]
                    known_count = sum(1 for p in people if p in person_ratings)
                    
                    person_features.append({
                        f'{prefix}_count': len(people),
                        f'{prefix}_avg_rating': np.mean(ratings),
                        f'{prefix}_max_rating': np.max(ratings),
                        f'{prefix}_min_rating': np.min(ratings),
                        f'{prefix}_known_count': known_count,
                    })
            
            person_df = pd.DataFrame(person_features, index=df.index)
            features = pd.concat([features, person_df], axis=1)
        
        # 5b. Franchise flag
        if 'collection_name' in df.columns:
            features['is_franchise'] = df['collection_name'].notna().astype(int)

        # 5c. Studio target encoding
        if 'studios' in df.columns:
            studio_features = []
            for _, row in df.iterrows():
                studios_str = row.get('studios', '')
                if not studios_str or pd.isna(studios_str):
                    studios = []
                else:
                    studios = [s.strip() for s in str(studios_str).split(',') if s.strip()]

                if not studios:
                    studio_features.append({
                        'stu_avg_rating': self.global_mean,
                        'stu_known_count': 0,
                    })
                else:
                    ratings = [self.studio_ratings.get(s, self.global_mean) for s in studios]
                    known = sum(1 for s in studios if s in self.studio_ratings)
                    studio_features.append({
                        'stu_avg_rating': np.mean(ratings),
                        'stu_known_count': known,
                    })
            features = pd.concat([features, pd.DataFrame(studio_features, index=df.index)], axis=1)

        # 6. Certificates (MPAA) - One-Hot
        if 'certificates' in df.columns:
            mppa = df['certificates'].apply(extract_certificate_mppa)
            for rating in ['G', 'PG', 'PG-13', 'R']:
                features[f'is_rated_{rating.replace("-", "")}'] = (mppa == rating).astype(int)
        
        # 7. Languages/Countries (Top 3 flags)
        if 'languages' in df.columns:
            for lang in ['English', 'Spanish', 'French', 'Japanese']:
                features[f'lang_{lang.lower()}'] = df['languages'].fillna('').str.contains(lang).astype(int)
                
        if 'countries' in df.columns:
            for country in ['USA', 'UK', 'Spain', 'France', 'Japan']:
                features[f'country_{country.lower()}'] = df['countries'].fillna('').str.contains(country).astype(int)

        # 7b. Keywords (multi-hot encoded with stored dynamic keywords)
        if 'keywords' in df.columns and self.selected_keywords:
            kw_features = df['keywords'].apply(
                lambda v: _multi_hot_keywords(v, self.selected_keywords)
            ).apply(pd.Series)
            features = pd.concat([features, kw_features], axis=1)

        # 8. Plot embeddings
        plots = df['plot'].fillna("").tolist()
        cached = None
        if use_cached_embeddings and 'plot_embedding' in df.columns:
            cached = df['plot_embedding'].tolist()
        
        embeddings = compute_embeddings(plots, cached)
        emb_cols = [f'plot_emb_{i}' for i in range(EMBEDDING_DIM)]
        emb_df = pd.DataFrame(embeddings, columns=emb_cols, index=df.index)
        features = pd.concat([features, emb_df], axis=1)
        
        return features
