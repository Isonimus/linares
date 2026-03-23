import random
from db import get_connection
from imdb_utils import search_imdb_movies, get_movie_details, DB_PATH
from config import RATING_SCALE

def get_or_create_user(conn, username):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE name = ?", (username,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO users (name) VALUES (?)", (username,))
    conn.commit()
    return cursor.lastrowid

def print_movie_info(m):
    """Prints movie info formatted for rating."""
    print(f"\n🎥 {m['title']} ({m.get('year', '????')})")
    print(f"🎭 {m.get('genres', 'Unknown')} | ⏱️ {m.get('runtime', '???')} min | ⭐ IMDb: {m.get('imdb_rating', '?.?')}/10")
    print(f"🎬 Dir: {m.get('directors', 'Unknown')}")
    print(f"🤝 Cast: {m.get('actors', 'Unknown')}\n")

def get_rating_choice(username):
    """Standardized rating input loop."""
    for key, data in RATING_SCALE.items():
        print(f"  [{key}] - {data['label']}")
    print("  [s] - Haven't seen it (Skip)")
    print("  [q] - Quit / Back to menu")

    while True:
        choice = input(f"\nYour choice [{username}]: ").strip().lower()
        if choice in ['q', 's'] or choice in RATING_SCALE:
            return choice
        print("⚠️ Invalid option. Please try again.")

def search_and_rate_specific(conn, user_id, username):
    """Search for a specific movie and rate it."""
    query_search = input("\nMovie title to search: ").strip()
    if not query_search: return

    print(f"🔍 Searching '{query_search}' on IMDb...")
    movies = search_imdb_movies(query_search)

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
    print("[0] Cancel")

    while True:
        try:
            choice = int(input("\nChoose an option (0-5): ").strip())
            if choice == 0: return
            if 1 <= choice <= len(top_picks):
                selected_movie_id = top_picks[choice - 1].get('id')
                break
            print("Option out of range.")
        except ValueError:
            print("Please enter a valid number.")
            
    # Fetch details (Centralized logic handles DB caching)
    m_details = get_movie_details(selected_movie_id)
    print_movie_info(m_details)
    
    choice = get_rating_choice(username)
    if choice == 'q': return
    if choice == 's': return
    
    data = RATING_SCALE[choice]
    label, score = data['label'], data['score']
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO ratings (user_id, movie_tconst, rating_label, rating_score)
        VALUES (?, ?, ?, ?)
    """, (user_id, selected_movie_id, label, score))
    conn.commit()
    print(f"✅ Saved! ({label})\n")

def rate_random_movies(conn, user_id, username):
    """Original logic: suggest popular unrated movies."""
    print("\nOptional filters (press Enter to skip):")
    filter_year = input("Year (e.g. 2010): ").strip()
    filter_genre = input("Genre (e.g. Sci-Fi): ").strip()
    
    cursor = conn.cursor()
    query = """
        SELECT tconst, title, year, genres, runtime, imdb_rating, directors, actors 
        FROM movies 
        WHERE tconst NOT IN (SELECT movie_tconst FROM ratings WHERE user_id = ?)
    """
    params = [user_id]
    
    if filter_year:
        query += " AND year = ?"
        params.append(int(filter_year))
    if filter_genre:
        query += " AND genres LIKE ?"
        params.append(f"%{filter_genre}%")
        
    query += " ORDER BY num_votes DESC LIMIT 200"
    
    cursor.execute(query, params)
    movies = cursor.fetchall()
    
    if not movies:
        print("\nNo movies found with these filters.")
        return

    random.shuffle(movies)

    print("\n" + "="*50)
    print("Let's rate some movies! (Press 'q' to return to the menu)")
    print("="*50)
    
    for row in movies:
        tconst, title, year, genres, runtime, imdb_rating, directors, actors = row
        m = {'title': title, 'year': year, 'genres': genres, 'runtime': runtime, 
             'imdb_rating': imdb_rating, 'directors': directors, 'actors': actors}
        print_movie_info(m)
        
        choice = get_rating_choice(username)
        if choice == 'q': break
        if choice == 's': 
            print("-" * 50)
            continue
            
        data = RATING_SCALE[choice]
        label, score = data['label'], data['score']
        cursor.execute("""
            INSERT OR REPLACE INTO ratings (user_id, movie_tconst, rating_label, rating_score)
            VALUES (?, ?, ?, ?)
        """, (user_id, tconst, label, score))
        conn.commit()
        print(f"✅ Saved! ({label})\n")
        print("-" * 50)

def rate_movies():
    conn = get_connection()
    print("\n🎬 LINARES: Rating Interface 🎬\n")
    
    username = input("Your profile name: ").strip()
    if not username: return

    user_id = get_or_create_user(conn, username)

    while True:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ratings WHERE user_id = ?", (user_id,))
        total_rated = cursor.fetchone()[0]

        print(f"\nProfile: {username} | Movies rated: {total_rated}")
        print("-" * 30)
        print("1. Suggest popular movies to rate (with filters)")
        print("2. Search and rate a specific movie")
        print("x. Exit")

        opcion = input("\nChoose an option: ").strip().lower()

        if opcion == '1':
            rate_random_movies(conn, user_id, username)
        elif opcion == '2':
            search_and_rate_specific(conn, user_id, username)
        elif opcion == 'x':
            break
        else:
            print("Invalid option.")

    conn.close()
    print(f"\nGoodbye, {username}!")

if __name__ == '__main__':
    rate_movies()
