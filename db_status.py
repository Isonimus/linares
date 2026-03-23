import sqlite3
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from db import DB_PATH

def get_status():
    console = Console()
    
    if not os.path.exists(DB_PATH):
        console.print(f"[bold red]Error:[/] Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # General Stats
    cursor.execute("SELECT COUNT(*) FROM movies")
    total_movies = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM ratings")
    total_ratings = cursor.fetchone()[0]

    # Helper function - check for NULL, empty, 'Unknown', or 'None' string
    def count_missing(column):
        cursor.execute(f"""
            SELECT COUNT(*) FROM movies 
            WHERE {column} IS NULL 
               OR {column} = '' 
               OR {column} = 'Unknown'
               OR {column} = 'None'
        """)
        return cursor.fetchone()[0]

    # ML Readiness
    cursor.execute("SELECT COUNT(*) FROM movies WHERE plot_embedding IS NOT NULL")
    with_embeddings = cursor.fetchone()[0]

    # UI Rendering
    console.print(Panel.fit("[bold blue]LINARES Context Engine - Database Status[/]", border_style="blue"))
    
    # Overview Table
    overview = Table(title="General Overview", title_style="bold magenta")
    overview.add_column("Metric", style="cyan")
    overview.add_column("Value", justify="right", style="green")
    
    overview.add_row("Total Movies", str(total_movies))
    overview.add_row("Total Users", str(total_users))
    overview.add_row("Total Ratings", str(total_ratings))
    overview.add_row("Movies with Embeddings", f"{with_embeddings} ({with_embeddings/total_movies*100:.1f}%)" if total_movies > 0 else "0")
    
    console.print(overview)
    
    # Quality Table - Essential Fields (needed for display)
    quality = Table(title="Essential Fields (Display)", title_style="bold yellow")
    quality.add_column("Field", style="cyan")
    quality.add_column("Missing", justify="right", style="red")
    quality.add_column("Coverage", justify="right", style="green")
    
    essential_fields = [
        ("Plot", "plot"),
        ("Poster", "poster_url"),
        ("Directors", "directors"),
        ("Writers", "writers"),
        ("Actors", "actors"),
    ]
    
    for name, column in essential_fields:
        missing = count_missing(column)
        coverage = ((total_movies - missing) / total_movies * 100) if total_movies > 0 else 0
        style = "green" if coverage > 95 else "yellow" if coverage > 50 else "red"
        quality.add_row(name, str(missing), f"[{style}]{coverage:.1f}%[/]")
        
    console.print(quality)
    
    # ML Features Table
    ml_table = Table(title="ML Feature Fields (Training)", title_style="bold cyan")
    ml_table.add_column("Field", style="cyan")
    ml_table.add_column("Missing", justify="right", style="red")
    ml_table.add_column("Coverage", justify="right", style="green")
    ml_table.add_column("Notes", style="dim")
    
    ml_fields = [
        ("Composers", "composers", "From soundtrack data"),
        ("Certificates", "certificates", "MPAA ratings"),
        ("Languages", "languages", "For language preferences"),
        ("Countries", "countries", "For origin preferences"),
        ("Keywords", "keywords", "Thematic tags"),
    ]
    
    for name, column, note in ml_fields:
        missing = count_missing(column)
        coverage = ((total_movies - missing) / total_movies * 100) if total_movies > 0 else 0
        style = "green" if coverage > 80 else "yellow" if coverage > 50 else "red"
        ml_table.add_row(name, str(missing), f"[{style}]{coverage:.1f}%[/]", note)
        
    console.print(ml_table)

    # Advice section
    console.print("")
    if total_movies > 0:
        if with_embeddings < total_movies:
            console.print("[bold yellow]Tip:[/] Run `python fetch_metadata.py 500` to enrich movies missing plot/poster.")
        
        # Check if backfill would help (including 'None' string)
        cursor.execute("""
            SELECT COUNT(*) FROM movies 
            WHERE plot IS NOT NULL AND plot != '' AND plot != 'No synopsis available.'
              AND ((composers IS NULL OR composers = '' OR composers = 'Unknown' OR composers = 'None')
                   OR (certificates IS NULL OR certificates = '' OR certificates = 'Unknown' OR certificates = 'None')
                   OR (languages IS NULL OR languages = '' OR languages = 'Unknown' OR languages = 'None')
                   OR (countries IS NULL OR countries = '' OR countries = 'Unknown' OR countries = 'None')
                   OR (keywords IS NULL OR keywords = '' OR keywords = 'Unknown' OR keywords = 'None'))
        """)
        backfill_candidates = cursor.fetchone()[0]
        
        if backfill_candidates > 0:
            console.print(f"[bold cyan]Tip:[/] Run `python fetch_metadata.py 500 --backfill` to fill {backfill_candidates} partially enriched movies.")

    conn.close()

if __name__ == "__main__":
    get_status()
