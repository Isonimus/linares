import React from 'react';
import { Search as SearchIcon, Layers } from 'lucide-react';
import MovieCard from './MovieCard';

export default function SearchTab({
  searchQuery,
  searchResults,
  handleSearch,
  onMovieClick,
  onFindSimilar,
  similarTo,
  similarMovies,
  similarLoading,
}) {
  return (
    <>
      <header>
        <h1>Search & Rate</h1>
        <p className="header-subtitle">Find any movie, rate it, or explore similar titles</p>
      </header>

      <div className="search-container">
        <SearchIcon size={20} className="search-icon" />
        <input
          type="text"
          className="search-bar-large"
          placeholder="Search for any movie..."
          value={searchQuery}
          onChange={handleSearch}
          autoFocus
        />
      </div>

      <div className="movie-grid animate-in" style={{ marginTop: '2rem' }}>
        {searchResults.length > 0 ? (
          searchResults.map((result) => (
            <MovieCard
              key={result.id}
              movie={{
                tconst: result.id,
                title: result.l,
                year: result.y,
                genres: result.q || "Movie",
                poster_url: result.i ? result.i.imageUrl : null,
                rating_label: result.rating_label,
              }}
              isSearchItem
              onFindSimilar={onFindSimilar}
              onClick={() => onMovieClick(result, true)}
            />
          ))
        ) : searchQuery.length > 2 ? (
          <div className="empty-state">
            <SearchIcon size={48} />
            <p>No results found for "{searchQuery}"</p>
          </div>
        ) : (
          <div className="empty-state">
            <SearchIcon size={48} />
            <p>Start typing to search for movies...</p>
          </div>
        )}
      </div>

      {(similarTo || similarLoading) && (
        <>
          <div className="similar-section-header">
            <Layers size={16} />
            Similar to <span>{similarTo?.title}</span>
          </div>
          {similarLoading ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <p>Finding similar movies...</p>
            </div>
          ) : (
            <div className="movie-grid animate-in">
              {similarMovies.map((movie) => (
                <MovieCard
                  key={movie.tconst}
                  movie={movie}
                  onClick={() => onMovieClick(movie)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
