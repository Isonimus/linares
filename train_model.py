"""
Model training script for LINARES movie predictor.

Improvements over original:
- Multi-hot encoded genres
- Target-encoded director/writer/actor features
- Year as numeric with derived features (decade, is_classic, is_modern)
- IMDb rating as feature
- K-fold cross-validation for reliable metrics
- Regularization to prevent overfitting
- Pre-computed embeddings from database
- Returns detailed insights about user preferences
"""

import pandas as pd
import numpy as np
import json
import logging
import config

logger = logging.getLogger(__name__)
from catboost import CatBoostRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.feature_extraction.text import TfidfVectorizer
import sqlite3
import os
import re

from features import FeatureMetadata


def extract_keyword_preferences(df, min_rating=7.0):
    """
    Analyze user's keyword/tag preferences from their rated movies.
    
    Args:
        df: DataFrame with 'keywords' and 'rating_score' columns
        
    Returns:
        dict with 'favorites' (high-rated keywords) and 'avoided' (low-rated keywords)
    """
    if 'keywords' not in df.columns:
        return {'favorites': [], 'avoided': []}
    
    keyword_scores = {}  # keyword -> list of scores
    
    for _, row in df.iterrows():
        kw_str = row.get('keywords', '')
        if not kw_str or pd.isna(kw_str):
            continue
        score = row['rating_score']
        keywords = [k.strip() for k in str(kw_str).split(',') if k.strip()]
        for kw in keywords:
            if kw not in keyword_scores:
                keyword_scores[kw] = []
            keyword_scores[kw].append(score)
    
    # Calculate averages (min 3 appearances for reliability)
    keyword_stats = []
    for kw, scores in keyword_scores.items():
        if len(scores) >= 3:
            keyword_stats.append({
                'keyword': kw,
                'avg_score': round(sum(scores) / len(scores), 1),
                'count': len(scores)
            })
    
    keyword_stats.sort(key=lambda x: x['avg_score'], reverse=True)
    
    # Top liked and disliked
    global_mean = df['rating_score'].mean()
    favorites = [k for k in keyword_stats if k['avg_score'] >= global_mean + 0.5][:8]
    avoided = [k for k in keyword_stats if k['avg_score'] <= global_mean - 0.5][-5:]
    
    return {
        'favorites': favorites,
        'avoided': list(reversed(avoided))  # Worst first
    }


def analyze_popularity_preference(df):
    """
    Analyze whether user prefers mainstream blockbusters or hidden gems.
    
    Args:
        df: DataFrame with 'num_votes' and 'rating_score' columns
        
    Returns:
        dict with preference analysis
    """
    if 'num_votes' not in df.columns:
        return {'preference': 'unknown', 'details': {}}
    
    votes = pd.to_numeric(df['num_votes'], errors='coerce').fillna(0)
    scores = df['rating_score']
    
    # Categorize movies
    blockbusters = df[votes > 500000]  # 500k+ votes
    mainstream = df[(votes > 100000) & (votes <= 500000)]  # 100k-500k
    moderate = df[(votes > 10000) & (votes <= 100000)]  # 10k-100k
    obscure = df[votes <= 10000]  # <10k votes
    
    def safe_stats(subset):
        if len(subset) < 2:
            return None
        return {
            'avg_score': round(subset['rating_score'].mean(), 1),
            'count': len(subset)
        }
    
    stats = {
        'blockbusters': safe_stats(blockbusters),
        'mainstream': safe_stats(mainstream),
        'moderate': safe_stats(moderate),
        'obscure': safe_stats(obscure)
    }
    
    # Determine preference
    valid_stats = {k: v for k, v in stats.items() if v is not None}
    if len(valid_stats) < 2:
        preference = 'insufficient_data'
        summary = "Not enough variety in movie popularity to determine preference"
    else:
        # Compare scores
        obscure_score = stats.get('obscure', {}).get('avg_score', 0) if stats.get('obscure') else 0
        blockbuster_score = stats.get('blockbusters', {}).get('avg_score', 0) if stats.get('blockbusters') else 0
        mainstream_score = stats.get('mainstream', {}).get('avg_score', 0) if stats.get('mainstream') else 0
        
        # Calculate correlation between votes and rating
        if len(df) >= 10:
            correlation = votes.corr(scores)
        else:
            correlation = 0
        
        if obscure_score > blockbuster_score + 0.5 and obscure_score > mainstream_score + 0.3:
            preference = 'hidden_gem_hunter'
            summary = "You tend to rate lesser-known films higher than blockbusters"
        elif blockbuster_score > obscure_score + 0.5:
            preference = 'blockbuster_fan'
            summary = "You tend to enjoy popular mainstream films"
        elif correlation > 0.15:
            preference = 'quality_aligns_with_popularity'
            summary = "Your ratings correlate with general popularity"
        elif correlation < -0.15:
            preference = 'contrarian'
            summary = "You often rate against the crowd"
        else:
            preference = 'balanced'
            summary = "You appreciate both mainstream and indie films equally"
    
    return {
        'preference': preference,
        'summary': summary,
        'by_popularity': stats,
        'correlation': round(votes.corr(scores), 2) if len(df) >= 10 else None
    }


def analyze_international_taste(df):
    """
    Analyze user's preferences for different languages and countries of origin.
    
    Args:
        df: DataFrame with 'languages', 'countries', and 'rating_score' columns
        
    Returns:
        dict with language and country preferences
    """
    result = {
        'languages': [],
        'countries': [],
        'prefers_hollywood': None,
        'favorite_foreign': None
    }
    
    # Analyze languages
    if 'languages' in df.columns:
        lang_scores = {}
        for _, row in df.iterrows():
            lang_str = row.get('languages', '')
            if not lang_str or pd.isna(lang_str):
                continue
            score = row['rating_score']
            # Primary language is first
            primary_lang = str(lang_str).split(',')[0].strip()
            if primary_lang and primary_lang not in ['None', 'Unknown', '']:
                if primary_lang not in lang_scores:
                    lang_scores[primary_lang] = []
                lang_scores[primary_lang].append(score)
        
        for lang, scores in lang_scores.items():
            if len(scores) >= 3:
                result['languages'].append({
                    'language': lang,
                    'avg_score': round(sum(scores) / len(scores), 1),
                    'count': len(scores)
                })
        result['languages'].sort(key=lambda x: x['avg_score'], reverse=True)
    
    # Analyze countries
    if 'countries' in df.columns:
        country_scores = {}
        for _, row in df.iterrows():
            country_str = row.get('countries', '')
            if not country_str or pd.isna(country_str):
                continue
            score = row['rating_score']
            # Primary country is first
            primary_country = str(country_str).split(',')[0].strip()
            if primary_country and primary_country not in ['None', 'Unknown', '']:
                if primary_country not in country_scores:
                    country_scores[primary_country] = []
                country_scores[primary_country].append(score)
        
        for country, scores in country_scores.items():
            if len(scores) >= 3:
                result['countries'].append({
                    'country': country,
                    'avg_score': round(sum(scores) / len(scores), 1),
                    'count': len(scores)
                })
        result['countries'].sort(key=lambda x: x['avg_score'], reverse=True)
        
        # Hollywood vs Foreign analysis
        usa_stats = next((c for c in result['countries'] if c['country'] in ['United States', 'USA']), None)
        foreign_stats = [c for c in result['countries'] if c['country'] not in ['United States', 'USA']]
        
        if usa_stats and foreign_stats:
            foreign_avg = sum(c['avg_score'] * c['count'] for c in foreign_stats) / sum(c['count'] for c in foreign_stats)
            result['prefers_hollywood'] = usa_stats['avg_score'] > foreign_avg + 0.3
            if foreign_stats:
                result['favorite_foreign'] = foreign_stats[0]['country']
    
    return result


# Maps country-specific ratings to MPAA equivalents for normalised maturity analysis.
# Covers the most common systems found in the database (Canada, Australia, UK, plus
# direct MPAA values that may appear without a country prefix).
_MATURITY_MAP = {
    # Direct MPAA (no country prefix)
    'G': 'G', 'PG': 'PG', 'PG-13': 'PG-13', 'R': 'R', 'NC-17': 'NC-17',
    # USA / United States
    'USA:G': 'G', 'USA:PG': 'PG', 'USA:PG-13': 'PG-13', 'USA:R': 'R', 'USA:NC-17': 'NC-17',
    'United States:G': 'G', 'United States:PG': 'PG', 'United States:PG-13': 'PG-13',
    'United States:R': 'R', 'United States:NC-17': 'NC-17',
    # Australia
    'Australia:G': 'G', 'Australia:PG': 'PG',
    'Australia:M': 'PG-13', 'Australia:MA': 'R', 'Australia:MA15+': 'R',
    'Australia:R': 'R', 'Australia:R18+': 'R',
    'Australia:X18+': 'NC-17', 'Australia:RC': 'NC-17',
    # Canada
    'Canada:G': 'G', 'Canada:PG': 'PG', 'Canada:PG-13': 'PG-13',
    'Canada:13+': 'PG-13', 'Canada:14': 'PG-13', 'Canada:14A': 'PG-13', 'Canada:14+': 'PG-13',
    'Canada:16+': 'R', 'Canada:18': 'R', 'Canada:18A': 'R', 'Canada:18+': 'R',
    'Canada:R': 'R', 'Canada:AA': 'R',
    'Canada:A': 'NC-17', 'Canada:PA': 'NC-17',
    # United Kingdom
    'United Kingdom:U': 'G', 'United Kingdom:PG': 'PG',
    'United Kingdom:12': 'PG-13', 'United Kingdom:12A': 'PG-13',
    'United Kingdom:15': 'R', 'United Kingdom:18': 'R', 'United Kingdom:R18': 'NC-17',
}


def analyze_maturity_preference(df):
    """
    Analyze user's preference for different maturity/age ratings.

    Args:
        df: DataFrame with 'certificates' and 'rating_score' columns

    Returns:
        dict with maturity rating preferences
    """
    if 'certificates' not in df.columns:
        return {'ratings': [], 'preference': 'unknown'}

    rating_scores = {}  # normalised MPAA label -> list of scores

    for _, row in df.iterrows():
        cert_str = row.get('certificates', '')
        if not cert_str or pd.isna(cert_str):
            continue
        score = row['rating_score']

        # Try each certificate entry; take the first one that maps to a known rating
        mpaa = None
        for cert in str(cert_str).split(','):
            cert = cert.strip()
            if cert in _MATURITY_MAP:
                mpaa = _MATURITY_MAP[cert]
                break

        if mpaa:
            rating_scores.setdefault(mpaa, []).append(score)
    
    ratings = []
    for rating, scores in rating_scores.items():
        if len(scores) >= 2:
            ratings.append({
                'rating': rating,
                'avg_score': round(sum(scores) / len(scores), 1),
                'count': len(scores)
            })
    
    ratings.sort(key=lambda x: x['avg_score'], reverse=True)
    
    # Determine preference
    if not ratings:
        preference = 'unknown'
        summary = "Not enough rated movies have MPAA ratings"
    else:
        top_rating = ratings[0]['rating']
        if top_rating == 'R':
            preference = 'mature'
            summary = "You tend to prefer R-rated mature content"
        elif top_rating == 'PG-13':
            preference = 'balanced'
            summary = "You enjoy PG-13 films that balance accessibility with depth"
        elif top_rating in ['G', 'PG']:
            preference = 'family_friendly'
            summary = "You appreciate family-friendly and lighter content"
        elif top_rating == 'NC-17':
            preference = 'adult'
            summary = "You don't shy away from adult-only content"
        else:
            preference = 'varied'
            summary = "You watch films across all maturity ratings"
    
    return {
        'ratings': ratings,
        'preference': preference,
        'summary': summary
    }


def analyze_underlying_patterns(df):
    """
    Analyze raw data correlations to reveal underlying taste patterns.
    
    These patterns show direct relationships between movie attributes
    and user ratings, which may be masked by target-encoded features
    in the model (e.g., actor ratings capturing year preferences).
    
    Args:
        df: DataFrame with movie data and 'rating_score' column
        
    Returns:
        dict with pattern analysis
    """
    import numpy as np
    
    patterns = []
    
    # Year/Era correlation
    if 'year' in df.columns:
        year_corr = df['rating_score'].corr(pd.to_numeric(df['year'], errors='coerce'))
        if not pd.isna(year_corr):
            if year_corr < -0.15:
                old_movies = df[df['year'] < 1990]
                new_movies = df[df['year'] >= 2010]
                old_avg = old_movies['rating_score'].mean() if len(old_movies) > 3 else None
                new_avg = new_movies['rating_score'].mean() if len(new_movies) > 3 else None
                detail = None
                if old_avg and new_avg:
                    detail = f"Pre-1990 films: {old_avg:.1f} avg, Post-2010: {new_avg:.1f} avg"
                patterns.append({
                    'pattern': 'prefers_older_movies',
                    'description': 'You rate older movies significantly higher',
                    'detail': detail
                })
            elif year_corr > 0.15:
                patterns.append({
                    'pattern': 'prefers_newer_movies',
                    'description': 'You prefer more recent films'
                })
    
    # Runtime correlation
    if 'runtime' in df.columns:
        runtime_corr = df['rating_score'].corr(pd.to_numeric(df['runtime'], errors='coerce'))
        if not pd.isna(runtime_corr):
            if runtime_corr < -0.1:
                short_movies = df[df['runtime'] < 100]
                long_movies = df[df['runtime'] > 140]
                short_avg = short_movies['rating_score'].mean() if len(short_movies) > 3 else None
                long_avg = long_movies['rating_score'].mean() if len(long_movies) > 3 else None
                detail = None
                if short_avg and long_avg:
                    detail = f"Under 100min: {short_avg:.1f} avg, Over 140min: {long_avg:.1f} avg"
                patterns.append({
                    'pattern': 'prefers_shorter_movies',
                    'description': 'You tend to rate shorter movies higher',
                    'detail': detail
                })
            elif runtime_corr > 0.1:
                patterns.append({
                    'pattern': 'prefers_longer_movies',
                    'description': 'You enjoy longer, epic-length films'
                })
    
    # IMDb rating alignment
    if 'imdb_rating' in df.columns:
        imdb_corr = df['rating_score'].corr(pd.to_numeric(df['imdb_rating'], errors='coerce'))
        if not pd.isna(imdb_corr):
            if imdb_corr > 0.3:
                patterns.append({
                    'pattern': 'aligns_with_critics',
                    'description': 'Your taste aligns well with IMDb consensus'
                })
            elif imdb_corr < 0.1:
                patterns.append({
                    'pattern': 'independent_taste',
                    'description': 'You have independent taste - IMDb ratings don\'t predict yours'
                })
    
    # Popularity correlation (log votes)
    if 'num_votes' in df.columns:
        votes = pd.to_numeric(df['num_votes'], errors='coerce')
        log_votes = np.log10(votes.clip(lower=1))
        votes_corr = df['rating_score'].corr(log_votes)
        if not pd.isna(votes_corr):
            if votes_corr < -0.15:
                patterns.append({
                    'pattern': 'prefers_obscure',
                    'description': 'You rate hidden gems higher than blockbusters'
                })
            elif votes_corr > 0.15:
                patterns.append({
                    'pattern': 'prefers_popular',
                    'description': 'You tend to enjoy popular, well-known films'
                })
    
    return {
        'patterns': patterns
    }


def extract_plot_themes(df, min_rating=7.0, top_n=10):
    """
    Extract common themes/keywords from highly-rated movie plots using TF-IDF.
    
    Args:
        df: DataFrame with 'plot' and 'rating_score' columns
        min_rating: Minimum rating to consider a movie "liked"
        top_n: Number of top themes to return
        
    Returns:
        list: Top themes as dicts with 'theme' and 'score'
    """
    # Filter to highly-rated movies with valid plots
    liked_movies = df[
        (df['rating_score'] >= min_rating) & 
        (df['plot'].notna()) & 
        (df['plot'] != '') &
        (~df['plot'].isin(['No synopsis available.']))
    ]
    
    if len(liked_movies) < 3:
        return []
    
    plots = liked_movies['plot'].tolist()
    
    # Common stopwords + movie-specific ones to filter out
    stop_words = [
        # English stopwords
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
        'shall', 'can', 'need', 'dare', 'ought', 'used', 'it', 'its', 'this', 'that',
        'these', 'those', 'i', 'you', 'he', 'she', 'we', 'they', 'what', 'which', 'who',
        'whom', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
        'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there',
        'then', 'once', 'her', 'his', 'him', 'my', 'your', 'our', 'their', 'me', 'us',
        'them', 'myself', 'yourself', 'himself', 'herself', 'itself', 'ourselves',
        'themselves', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'under', 'again', 'further', 'while', 'about', 'against', 'up', 'down',
        'out', 'off', 'over', 'any', 'because', 'until', 'if', 'although', 'though',
        # Movie-plot specific stopwords
        'film', 'movie', 'story', 'tells', 'follows', 'finds', 'becomes', 'must', 'gets',
        'takes', 'makes', 'goes', 'comes', 'sets', 'turns', 'begins', 'starts', 'ends',
        'leads', 'brings', 'puts', 'gives', 'shows', 'sees', 'knows', 'thinks', 'wants',
        'tries', 'needs', 'helps', 'works', 'plays', 'lives', 'dies', 'meets', 'joins',
        'leaves', 'returns', 'discovers', 'learns', 'realizes', 'decides', 'attempts',
        'man', 'woman', 'young', 'old', 'new', 'one', 'two', 'first', 'last', 'time',
        'day', 'night', 'year', 'years', 'life', 'world', 'way', 'people', 'find',
        'take', 'make', 'come', 'go', 'get', 'know', 'think', 'see', 'want', 'look',
        'use', 'give', 'tell', 'work', 'call', 'try', 'ask', 'put', 'keep', 'let',
        'begin', 'seem', 'help', 'show', 'hear', 'play', 'run', 'move', 'live', 'believe',
        'hold', 'bring', 'happen', 'write', 'provide', 'sit', 'stand', 'lose', 'pay',
        'meet', 'include', 'continue', 'set', 'learn', 'change', 'lead', 'understand',
        'watch', 'follow', 'stop', 'create', 'speak', 'read', 'allow', 'add', 'spend',
        'grow', 'open', 'walk', 'win', 'offer', 'remember', 'love', 'consider', 'appear',
        'buy', 'wait', 'serve', 'die', 'send', 'expect', 'build', 'stay', 'fall', 'cut',
        'reach', 'kill', 'remain', 'however', 'along', 'soon', 'later', 'back', 'away',
        'still', 'even', 'well', 'together', 'around', 'yet', 'without', 'within',
        'across', 'behind', 'beyond', 'upon', 'toward', 'since', 'despite', 'among',
        'throughout', 'something', 'nothing', 'everything', 'someone', 'anyone', 'everyone',
        'another', 'being', 'having', 'doing', 'going', 'getting', 'making', 'taking'
    ]
    
    try:
        # Use TF-IDF to find distinctive terms
        vectorizer = TfidfVectorizer(
            max_features=200,
            stop_words=stop_words,
            ngram_range=(1, 2),  # Include bigrams for phrases
            min_df=2,  # Term must appear in at least 2 plots
            max_df=0.8,  # Ignore terms in >80% of plots
            token_pattern=r'\b[a-zA-Z]{3,}\b'  # Only words with 3+ letters
        )
        
        tfidf_matrix = vectorizer.fit_transform(plots)
        feature_names = vectorizer.get_feature_names_out()
        
        # Sum TF-IDF scores across all liked movies
        summed_tfidf = np.asarray(tfidf_matrix.sum(axis=0)).flatten()
        
        # Get top terms
        top_indices = summed_tfidf.argsort()[-top_n*2:][::-1]  # Get more, then filter
        
        themes = []
        seen_roots = set()
        
        for idx in top_indices:
            term = feature_names[idx]
            score = summed_tfidf[idx]
            
            # Skip if we've seen a similar term (simple dedup)
            root = term.split()[0][:5] if ' ' in term else term[:5]
            if root in seen_roots:
                continue
            seen_roots.add(root)
            
            # Capitalize nicely
            display_term = ' '.join(word.capitalize() for word in term.split())
            
            themes.append({
                'theme': display_term,
                'score': round(float(score), 2)
            })
            
            if len(themes) >= top_n:
                break
        
        return themes
        
    except Exception as e:
        logger.warning("Could not extract plot themes: %s", e)
        return []

from db import DB_PATH, DATA_DIR


def load_data(username):
    """Load rated movies for a user with all necessary columns."""
    conn = sqlite3.connect(DB_PATH)
    
    # Get user id
    user_df = pd.read_sql_query(
        "SELECT id FROM users WHERE LOWER(name) = ?",
        conn,
        params=[username.lower()]
    )
    if user_df.empty:
        logger.warning("User not found: %s", username)
        conn.close()
        return None
        
    user_id = user_df.iloc[0]['id']
    
    # Join ratings with movies - include all needed columns
    query = """
    SELECT 
        m.tconst,
        m.title,
        m.year,
        m.genres,
        m.runtime,
        m.imdb_rating,
        m.num_votes,
        m.directors,
        m.writers,
        m.actors,
        m.plot,
        m.plot_embedding,
        m.composers,
        m.certificates,
        m.languages,
        m.countries,
        m.keywords,
        r.rating_score
    FROM ratings r
    JOIN movies m ON r.movie_tconst = m.tconst
    WHERE r.user_id = ?
    """
    
    df = pd.read_sql_query(query, conn, params=[int(user_id)])
    conn.close()
    return df


def train(username, verbose=True):
    """
    Train a personalized movie rating model for a user.
    
    Args:
        username: User profile name
        verbose: Whether to print detailed output
        
    Returns:
        dict with training insights, or None if training failed
    """
    if verbose:
        logger.info(f"Loading ratings for user: {username}...")
    
    df = load_data(username)
    
    if df is None or len(df) < 10:
        if verbose:
            logger.info("Not enough data. Please rate at least 10 movies first.")
        return None
    
    if verbose:
        logger.info(f"Total rated movies found: {len(df)}")
    
    # Check how many have cached embeddings
    cached_count = df['plot_embedding'].notna().sum()
    if verbose:
        logger.info(f"Movies with pre-computed embeddings: {cached_count}/{len(df)}")
    
    # Prepare features
    if verbose:
        logger.info("\nPreparing features...")
        logger.info("  - Encoding genres (multi-hot)...")
        logger.info("  - Computing person features (target encoding)...")
        logger.info("  - Processing plot embeddings...")
    
    # Create feature metadata for inference later
    metadata = FeatureMetadata()
    metadata.fit(df)
    
    # Prepare features using training data for target encoding
    # Pass the dynamically selected keywords from metadata
    X = metadata.prepare_features(df, use_cached_embeddings=True)
    y = df['rating_score']
    
    if verbose:
        logger.info(f"\nDataset dimensions: {X.shape[0]} samples, {X.shape[1]} features")
        
        # Show feature groups
        n_genre = sum(1 for c in X.columns if c.startswith('genre_'))
        n_combo = sum(1 for c in X.columns if c.startswith('combo_'))
        n_kw = sum(1 for c in X.columns if c.startswith('kw_'))
        n_person = sum(1 for c in X.columns if any(c.startswith(p) for p in ['dir_', 'wri_', 'act_', 'stu_', 'com_']))
        n_emb = sum(1 for c in X.columns if c.startswith('plot_emb_'))
        n_other = X.shape[1] - n_genre - n_combo - n_kw - n_person - n_emb
        logger.info(f"  - Base features: {n_other}")
        logger.info(f"  - Genre features: {n_genre}")
        logger.info(f"  - Genre combinations: {n_combo}")
        logger.info(f"  - Keyword features: {n_kw} (dynamic)")
        logger.info(f"  - Person features: {n_person}")
        logger.info(f"  - Embedding dimensions: {n_emb}")
    
    # K-Fold Cross-Validation
    n_splits = min(5, len(df) // 5)  # At least 5 samples per fold
    if n_splits < 2:
        n_splits = 2
    
    if verbose:
        logger.info(f"\n📊 Running {n_splits}-Fold Cross-Validation...")
    
    # Cross-validation predictions
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    cv_predictions = np.zeros(len(y))
    fold_maes = []
    
    for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        fold_model = CatBoostRegressor(
            iterations=300,
            learning_rate=0.03,
            depth=3,
            l2_leaf_reg=5,
            min_data_in_leaf=3,
            loss_function='RMSE',
            verbose=0,
            random_seed=42,
            train_dir=os.path.join(DATA_DIR, 'catboost_info'),
        )
        fold_model.fit(X_train, y_train)
        
        fold_preds = fold_model.predict(X_val)
        cv_predictions[val_idx] = fold_preds
        
        fold_mae = mean_absolute_error(y_val, fold_preds)
        fold_maes.append(fold_mae)
        if verbose:
            logger.info(f"  Fold {fold + 1}: MAE = {fold_mae:.2f}")
    
    # Overall CV metrics
    cv_mae = mean_absolute_error(y, cv_predictions)
    cv_r2 = r2_score(y, cv_predictions)
    cv_mae_std = np.std(fold_maes)
    
    if verbose:
        logger.info("\n" + "="*60)
        logger.info("🎯 TRAINING RESULTS 🎯")
        logger.info("="*60)
        logger.info(f"\n📈 Accuracy Metrics:")
        logger.info(f"   Mean Absolute Error (MAE): {cv_mae:.2f} ± {cv_mae_std:.2f} points")
        logger.info(f"   R-squared (R²): {cv_r2:.2f}")
        logger.info(f"\n   Interpretation: On average, the model is off by {cv_mae:.2f} points")
        logger.info(f"   on a scale of 0 to 10 when predicting your score.")

        if cv_mae < 1.0:
            logger.info("   ✅ Excellent accuracy!")
        elif cv_mae < 1.5:
            logger.info("   ✅ Good accuracy.")
        elif cv_mae < 2.0:
            logger.info("   ⚠️ Acceptable accuracy. More ratings will improve the model.")
        else:
            logger.info("   ⚠️ Low accuracy. You need to rate more movies.")

    # Train final model on all data
    if verbose:
        logger.info("\n" + "-"*60)
        logger.info("Training final model on all data...")
    
    model = CatBoostRegressor(
        iterations=300,
        learning_rate=0.03,
        depth=3,
        l2_leaf_reg=5,
        min_data_in_leaf=3,
        loss_function='RMSE',
        verbose=100 if verbose else 0,
        random_seed=42,
        train_dir=os.path.join(DATA_DIR, 'catboost_info'),
    )
    model.fit(X, y)
    
    # ==========================================
    # INSIGHTS SECTION
    # ==========================================
    
    # Feature Importance Analysis
    feature_importances = model.get_feature_importance()
    importance_df = pd.DataFrame({
        'feature': X.columns,
        'importance': feature_importances
    }).sort_values('importance', ascending=False)
    
    # Categorize top features for insights
    top_features = []
    for _, row in importance_df.head(10).iterrows():
        feature_name = row['feature']
        importance = row['importance']
        
        # Interpret the feature
        if feature_name.startswith('act_'):
            category = "Actors"
            if 'avg' in feature_name:
                interpretation = "Your rating correlates strongly with how you've rated these actors before"
            elif 'min' in feature_name:
                interpretation = "The lowest-rated actor in a movie affects your enjoyment"
            elif 'max' in feature_name:
                interpretation = "Having at least one actor you like matters"
            else:
                interpretation = "Actor-related feature"
        elif feature_name.startswith('dir_'):
            category = "Directors"
            interpretation = "Director preference influences your ratings"
        elif feature_name.startswith('wri_'):
            category = "Writers"
            interpretation = "Writer/screenplay quality matters to you"
        elif feature_name.startswith('com_'):
            category = "Composers"
            interpretation = "Musical score quality and style matter to you"
        elif feature_name.startswith('genre_'):
            category = "Genre"
            genre = feature_name.replace('genre_', '')
            interpretation = f"Your affinity for {genre} movies"
        elif feature_name.startswith('plot_emb_'):
            category = "Plot/Story"
            interpretation = "Story themes and narrative elements"
        elif feature_name == 'imdb_rating':
            category = "Quality"
            interpretation = "You tend to agree with general audience ratings"
        elif feature_name.startswith('is_rated_'):
            category = "Maturity"
            interpretation = "Age rating/tone of the movie affects you"
        elif feature_name.startswith('lang_'):
            category = "Language"
            interpretation = "Original language of the film is a factor"
        elif feature_name.startswith('country_'):
            category = "Country"
            interpretation = "Country of origin preference"
        elif feature_name in ['year', 'years_since_release', 'decade']:
            category = "Era"
            interpretation = "Movie era/age affects your enjoyment"
        elif feature_name == 'runtime':
            category = "Length"
            interpretation = "Movie duration matters to you"
        elif feature_name.startswith('kw_'):
            category = "Keywords"
            keyword = feature_name.replace('kw_', '').replace('-', ' ').title()
            interpretation = f"You enjoy movies tagged with '{keyword}'"
        elif feature_name == 'log_votes':
            category = "Popularity"
            interpretation = "How well-known a movie is affects your rating"
        elif feature_name == 'is_popular':
            category = "Popularity"
            interpretation = "Whether a movie is mainstream (100k+ votes) matters"
        elif feature_name == 'is_obscure':
            category = "Popularity"
            interpretation = "Whether a movie is a hidden gem (<10k votes) matters"
        elif feature_name in ['is_classic', 'is_modern']:
            category = "Era"
            interpretation = "Classic vs modern era preference"
        elif feature_name in ['is_short', 'is_long']:
            category = "Length"
            interpretation = "Movie duration preference"
        elif feature_name.startswith('combo_'):
            category = "Genre Combo"
            # Parse combo_Action_Sci-Fi -> "Action + Sci-Fi"
            parts = feature_name.replace('combo_', '').split('_')
            if len(parts) == 2:
                combo_name = f"{parts[0]} + {parts[1]}"
            else:
                combo_name = feature_name
            interpretation = f"You have a specific preference for {combo_name} hybrids"
        else:
            category = "Other"
            interpretation = feature_name
        
        top_features.append({
            'feature': feature_name,
            'category': category,
            'importance': round(importance, 1),
            'interpretation': interpretation
        })
    
    # Genre preferences
    genre_cols = [c for c in X.columns if c.startswith('genre_') and X[c].sum() > 0]
    genre_preferences = []
    for gc in genre_cols:
        mask = X[gc] == 1
        if mask.sum() >= 2:  # At least 2 movies
            avg = float(y[mask].mean())
            count = int(mask.sum())
            genre_preferences.append({
                'genre': gc.replace('genre_', ''),
                'avg_score': round(avg, 1),
                'count': count
            })
    
    genre_preferences.sort(key=lambda x: x['avg_score'], reverse=True)
    top_genres = genre_preferences[:5]
    bottom_genres = genre_preferences[-3:] if len(genre_preferences) > 5 else []
    
    def extract_person_prefs(category):
        prefs = []
        for name, data in metadata.person_ratings.get(category, {}).items():
            prefs.append({'name': name, 'avg_score': round(data.get('avg', 0), 1), 'count': data.get('count', 0)})
        prefs.sort(key=lambda x: x['avg_score'], reverse=True)
        return prefs
    
    # Person preferences (from metadata)
    director_prefs = extract_person_prefs('directors')
    actor_prefs = extract_person_prefs('actors')
    writer_prefs = extract_person_prefs('writers')
    composer_prefs = extract_person_prefs('composers')
    
    # Era preferences
    df['decade'] = (df['year'] // 10) * 10
    decade_prefs = []
    for decade, group in df.groupby('decade'):
        if len(group) >= 2:
            decade_prefs.append({
                'decade': f"{int(decade)}s",
                'avg_score': round(group['rating_score'].mean(), 1),
                'count': len(group)
            })
    decade_prefs.sort(key=lambda x: x['avg_score'], reverse=True)
    
    # Extract plot themes from highly-rated movies
    plot_themes = extract_plot_themes(df, min_rating=7.0, top_n=8)
    
    # NEW: Extract keyword preferences
    keyword_prefs = extract_keyword_preferences(df, min_rating=7.0)
    
    # NEW: Analyze popularity preference
    popularity_pref = analyze_popularity_preference(df)
    
    # NEW: Analyze international taste
    international_taste = analyze_international_taste(df)
    
    # NEW: Analyze maturity rating preference
    maturity_pref = analyze_maturity_preference(df)
    
    # NEW: Analyze underlying data patterns (raw correlations)
    underlying_patterns = analyze_underlying_patterns(df)
    
    # Build insights object
    insights = {
        'metrics': {
            'mae': round(cv_mae, 2),
            'mae_std': round(cv_mae_std, 2),
            'r2': round(cv_r2, 2),
            'total_ratings': len(df),
            'avg_rating': round(float(y.mean()), 1),
            'rating_std': round(float(y.std()), 1)
        },
        'top_features': top_features,
        'genre_preferences': {
            'favorites': top_genres,
            'least_favorites': bottom_genres
        },
        'favorite_directors': director_prefs[:5],
        'favorite_actors': actor_prefs[:5],
        'favorite_writers': writer_prefs[:5],
        'favorite_composers': composer_prefs[:5],
        'era_preferences': decade_prefs[:5],
        'plot_themes': plot_themes,
        'keyword_preferences': keyword_prefs,
        'popularity_preference': popularity_pref,
        'international_taste': international_taste,
        'maturity_preference': maturity_pref,
        'underlying_patterns': underlying_patterns,
        'what_matters_most': _generate_what_matters_summary(importance_df)
    }
    
    # Print insights
    if verbose:
        logger.info("\n" + "="*60)
        logger.info("🔍 INSIGHTS INTO YOUR FILM TASTE 🔍")
        logger.info("="*60)

        logger.info(f"\n💡 What influences your ratings most:")
        for line in insights['what_matters_most']:
            logger.info(f"   • {line}")

        logger.info(f"\n📊 Top 10 predictive features:")
        for feat in top_features:
            bar = "█" * int(feat['importance'] / 3)
            logger.info(f"   {feat['feature'][:22]:22} {feat['importance']:5.1f}% {bar}")

        logger.info(f"\n🎭 Your favourite genres:")
        for g in top_genres:
            stars = "★" * int(g['avg_score'] / 2)
            logger.info(f"   {g['genre']:15} {g['avg_score']}/10 {stars} ({g['count']} films)")

        if bottom_genres:
            logger.info(f"\n   Genres you enjoy least:")
            for g in bottom_genres:
                logger.info(f"   {g['genre']:15} {g['avg_score']}/10 ({g['count']} films)")

        if director_prefs:
            logger.info(f"\n🎬 Your favourite directors:")
            for d in director_prefs[:5]:
                logger.info(f"   {d['name'][:30]:30} {d['avg_score']}/10")

        if actor_prefs:
            logger.info(f"\n🌟 Your favourite actors:")
            for a in actor_prefs[:5]:
                logger.info(f"   {a['name'][:30]:30} {a['avg_score']}/10")

        if composer_prefs:
            logger.info(f"\n🎵 Your favourite composers:")
            for c in composer_prefs[:5]:
                logger.info(f"   {c['name'][:30]:30} {c['avg_score']}/10")

        if decade_prefs:
            logger.info(f"\n📅 Your favourite eras:")
            for e in decade_prefs[:3]:
                logger.info(f"   {e['decade']:10} {e['avg_score']}/10 ({e['count']} films)")
        
        # NEW: Keyword preferences
        if keyword_prefs.get('favorites'):
            logger.info(f"\n🏷️ Your favourite tags/themes:")
            for k in keyword_prefs['favorites'][:5]:
                logger.info(f"   {k['keyword'][:25]:25} {k['avg_score']}/10 ({k['count']} films)")

        # NEW: Popularity preference
        if popularity_pref.get('preference') != 'insufficient_data':
            logger.info(f"\n📊 Your popularity profile:")
            logger.info(f"   {popularity_pref.get('summary', '')}")
            if popularity_pref.get('correlation') is not None:
                corr = popularity_pref['correlation']
                if corr > 0.1:
                    logger.info(f"   Votes-score correlation: +{corr:.2f} (you tend to rate popular films higher)")
                elif corr < -0.1:
                    logger.info(f"   Votes-score correlation: {corr:.2f} (you seek hidden gems)")

        # NEW: International taste
        if international_taste.get('countries'):
            logger.info(f"\n🌍 Your favourite countries of origin:")
            for c in international_taste['countries'][:4]:
                logger.info(f"   {c['country'][:20]:20} {c['avg_score']}/10 ({c['count']} films)")
        if international_taste.get('languages'):
            logger.info(f"\n🗣️ Original languages you prefer:")
            for l in international_taste['languages'][:4]:
                logger.info(f"   {l['language'][:15]:15} {l['avg_score']}/10 ({l['count']} films)")

        # NEW: Maturity preference
        if maturity_pref.get('ratings'):
            logger.info(f"\n🔞 Your content rating preference:")
            logger.info(f"   {maturity_pref.get('summary', '')}")
            for r in maturity_pref['ratings'][:3]:
                logger.info(f"   {r['rating']:8} {r['avg_score']}/10 ({r['count']} films)")

        # NEW: Underlying patterns
        if underlying_patterns.get('patterns'):
            logger.info(f"\n🔬 Underlying patterns in your data:")
            for p in underlying_patterns['patterns']:
                logger.info(f"   • {p['description']}")
                if p.get('detail'):
                    logger.info(f"     ({p['detail']})")
        
        logger.info("\n" + "="*60)
    
    # Save the model
    model_path = os.path.join(DATA_DIR, f'model_{username}.cbm')
    model.save_model(model_path)
    if verbose:
        logger.info(f"\n✅ Model saved to: {model_path}")

    # Save feature metadata for inference
    metadata_path = os.path.join(DATA_DIR, f'model_{username}_metadata.json')
    metadata.save(metadata_path)
    if verbose:
        logger.info(f"✅ Metadata saved to: {metadata_path}")

    # Save insights
    insights_path = os.path.join(DATA_DIR, f'model_{username}_insights.json')
    with open(insights_path, 'w', encoding='utf-8') as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)
    if verbose:
        logger.info(f"✅ Insights saved to: {insights_path}")
    
    return insights


def _categorise_feature(feature_name):
    """Map a raw feature name to its display category."""
    if feature_name.startswith('act_'):
        return "Actors"
    elif feature_name.startswith('dir_'):
        return "Directors"
    elif feature_name.startswith('wri_'):
        return "Writers"
    elif feature_name.startswith('com_'):
        return "Composers"
    elif feature_name.startswith('genre_'):
        return "Genre"
    elif feature_name.startswith('combo_'):
        return "Genre Combo"
    elif feature_name.startswith('plot_emb_'):
        return "Plot/Story"
    elif feature_name.startswith('kw_'):
        return "Keywords"
    elif feature_name.startswith('lang_'):
        return "Language"
    elif feature_name.startswith('country_'):
        return "Country"
    elif feature_name.startswith('is_rated_'):
        return "Maturity"
    elif feature_name in ['year', 'years_since_release', 'decade', 'is_classic', 'is_modern']:
        return "Era"
    elif feature_name in ['runtime', 'is_short', 'is_long']:
        return "Length"
    elif feature_name == 'imdb_rating':
        return "Quality"
    elif feature_name in ['log_votes', 'is_popular', 'is_obscure']:
        return "Popularity"
    return None


def _generate_what_matters_summary(importance_df):
    """Generate a human-readable summary of what matters most.

    Uses the full importance_df (all features) so that categories with many
    low-importance features (plot embeddings, genre dummies) are not
    under-credited compared to categories with a few high-importance ones.
    """
    summary = []

    # Sum importance across ALL features per category
    categories = {}
    for _, row in importance_df.iterrows():
        cat = _categorise_feature(row['feature'])
        if cat is None:
            continue
        categories[cat] = categories.get(cat, 0) + row['importance']

    # Normalise so percentages reflect share of total attributed importance
    total = sum(categories.values()) or 1
    categories = {cat: imp / total * 100 for cat, imp in categories.items()}

    # Sort by total importance
    sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
    
    for cat, importance in sorted_cats[:3]:
        if cat == "Actors":
            summary.append(f"CAST is key ({importance:.0f}% importance) - You tend to enjoy films with actors you've liked before")
        elif cat == "Directors":
            summary.append(f"DIRECTORS matter ({importance:.0f}%) - You follow certain directors")
        elif cat == "Genre":
            summary.append(f"GENRE influences you ({importance:.0f}%) - You have clear genre preferences")
        elif cat == "Plot/Story":
            summary.append(f"STORY matters ({importance:.0f}%) - The type of narrative affects your enjoyment")
        elif cat == "Quality":
            summary.append(f"OVERALL QUALITY ({importance:.0f}%) - You tend to agree with IMDb ratings")
        elif cat == "Era":
            summary.append(f"ERA ({importance:.0f}%) - You prefer films from certain decades")
        elif cat == "Composers":
            summary.append(f"MUSIC ({importance:.0f}%) - The soundtrack is key to your enjoyment")
        elif cat == "Maturity":
            summary.append(f"TONE/RATING ({importance:.0f}%) - The certification (R, PG-13) influences your taste")
        elif cat == "Keywords":
            summary.append(f"THEMES/TAGS ({importance:.0f}%) - Certain themes (heist, time-travel, revenge...) predict your taste")
        elif cat == "Popularity":
            summary.append(f"POPULARITY ({importance:.0f}%) - How well-known a film is affects your rating")
        elif cat == "Language":
            summary.append(f"LANGUAGE ({importance:.0f}%) - The original language of the film affects your taste")
        elif cat == "Country":
            summary.append(f"COUNTRY OF ORIGIN ({importance:.0f}%) - You prefer cinema from certain countries")
        elif cat == "Genre Combo":
            summary.append(f"GENRE COMBINATIONS ({importance:.0f}%) - You enjoy certain hybrids (e.g. Sci-Fi + Drama, Action + Comedy)")
        elif cat == "Length":
            summary.append(f"RUNTIME ({importance:.0f}%) - The length of the film affects your enjoyment")

    if not summary:
        summary.append("Your model is learning your preferences")
    
    return summary


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    user = input("Enter your profile name to train the model: ").strip()
    if user:
        train(user)
    else:
        logger.warning("No profile name entered.")
