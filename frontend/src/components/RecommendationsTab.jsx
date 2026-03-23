import React from 'react';
import { Filter, RefreshCw, Film, ChevronRight } from 'lucide-react';
import MovieCard from './MovieCard';
import FactorPills from './FactorPills';

export default function RecommendationsTab({
  recommendations,
  loading,
  error,
  genres,
  selectedGenre,
  setSelectedGenre,
  selectedFactor,
  setSelectedFactor,
  hasMoreRecs,
  fetchRecommendations,
  onMovieClick,
}) {
  return (
    <>
      <header>
        <h1>Handpicked for You</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div className="filter-container">
            <Filter size={18} />
            <select
              value={selectedGenre}
              onChange={(e) => setSelectedGenre(e.target.value)}
              className="genre-filter"
            >
              <option value="">All Genres</option>
              {genres.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <button onClick={() => fetchRecommendations()} className="refresh-btn glass" disabled={loading}>
            <RefreshCw size={18} className={loading ? 'spinning' : ''} />
          </button>
        </div>
      </header>
      <FactorPills value={selectedFactor} onChange={setSelectedFactor} />

      {error && <div className="error-message">{error}</div>}

      <div className="movie-grid animate-in">
        {loading ? (
          <div className="loading-container">
            <RefreshCw size={32} className="spinning" />
            <p>Analyzing your taste...</p>
          </div>
        ) : recommendations.length > 0 ? (
          recommendations.map((movie) => (
            <MovieCard key={movie.tconst} movie={movie} onClick={() => onMovieClick(movie)} />
          ))
        ) : !error && (
          <div className="empty-state">
            <Film size={48} />
            <p>No recommendations available.</p>
            <p className="hint">Try rating more movies or train your model in Settings.</p>
          </div>
        )}
      </div>

      {hasMoreRecs && recommendations.length > 0 && !loading && (
        <div className="pagination-controls" style={{ display: 'flex', justifyContent: 'center', marginTop: '2rem', paddingBottom: '2rem' }}>
          <button
            className="action-btn glass"
            onClick={() => fetchRecommendations(true)}
            style={{ minWidth: '200px' }}
          >
            <ChevronRight size={18} />
            <span>Load more movies</span>
          </button>
        </div>
      )}
    </>
  );
}
