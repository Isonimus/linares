import sqlite3
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
DB_PATH = os.path.join(DATA_DIR, 'movies.db')

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create movies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            tconst TEXT PRIMARY KEY,
            title TEXT,
            year INTEGER,
            genres TEXT,
            runtime INTEGER,
            imdb_rating REAL,
            num_votes INTEGER,
            plot TEXT,
            directors TEXT,
            writers TEXT,
            actors TEXT,
            poster_url TEXT,
            plot_embedding BLOB,
            composers TEXT,
            certificates TEXT,
            languages TEXT,
            countries TEXT,
            keywords TEXT
        )
    ''')
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')
    
    # Create ratings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            movie_tconst TEXT,
            rating_label TEXT,
            rating_score REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(movie_tconst) REFERENCES movies(tconst),
            UNIQUE(user_id, movie_tconst)
        )
    ''')
    
    # Migration: Add poster_url if not exists
    try:
        cursor.execute("ALTER TABLE movies ADD COLUMN poster_url TEXT")
    except sqlite3.OperationalError:
        pass # Column already exists
    
    # Migration: Add plot_embedding if not exists
    try:
        cursor.execute("ALTER TABLE movies ADD COLUMN plot_embedding BLOB")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    # Migrations for new ML features
    new_columns = [
        "composers TEXT", "certificates TEXT", "languages TEXT", "countries TEXT", "keywords TEXT",
        "collection_name TEXT", "studios TEXT",
    ]
    for col in new_columns:
        try:
            cursor.execute(f"ALTER TABLE movies ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass # Column already exists
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
