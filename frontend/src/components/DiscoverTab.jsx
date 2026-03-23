import React from 'react';
import { Film, RefreshCw, Shuffle, SkipForward, CheckCircle, Star } from 'lucide-react';

export default function DiscoverTab({
  randomMovies,
  randomIndex,
  randomFilterYear,
  setRandomFilterYear,
  randomFilterGenre,
  setRandomFilterGenre,
  randomSessionStats,
  loading,
  error,
  ratingLoading,
  ratingsConfig,
  genres,
  startRandomSession,
  handleRandomRating,
  skipRandomMovie,
}) {
  return (
    <>
      <header>
        <h1>Rate Random Movies</h1>
        <p className="header-subtitle">Build your taste profile by rating popular movies</p>
      </header>

      <div className="random-controls glass">
        <div className="session-stat">
          <CheckCircle size={16} />
          <span>{randomSessionStats.rated} rated</span>
        </div>
        <div className="session-stat">
          <SkipForward size={16} />
          <span>{randomSessionStats.skipped} skipped</span>
        </div>
        <div className="session-progress">
          <span>{randomIndex + 1} / {randomMovies.length}</span>
        </div>

        <div className="controls-divider" />

        <div className="random-filters-group">
          <div className="filter-group">
            <label>Year</label>
            <input
              type="number"
              placeholder="e.g. 2010"
              value={randomFilterYear}
              onChange={(e) => setRandomFilterYear(e.target.value)}
              className="filter-input"
            />
          </div>
          <div className="filter-group">
            <label>Genre</label>
            <select
              value={randomFilterGenre}
              onChange={(e) => setRandomFilterGenre(e.target.value)}
              className="filter-select"
            >
              <option value="">All Genres</option>
              {genres.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <button className="filter-apply-btn" onClick={startRandomSession}>
            <Shuffle size={16} />
            New Batch
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading ? (
        <div className="loading-container">
          <RefreshCw size={32} className="spinning" />
          <p>Finding movies for you...</p>
        </div>
      ) : randomMovies.length > 0 ? (
        <div className="random-rating-container animate-in">
          {(() => {
            const movie = randomMovies[randomIndex];
            const hasValidPoster = movie.poster_url && !movie.poster_url.includes('placeholder');
            return (
              <div className="random-movie-card glass">
                <div className="random-movie-top">
                  <div className="random-movie-poster">
                    {hasValidPoster ? (
                      <img src={movie.poster_url} alt={movie.title} />
                    ) : (
                      <div className="random-poster-placeholder">
                        <Film size={48} />
                        <span>{movie.title?.charAt(0) || '?'}</span>
                      </div>
                    )}
                  </div>
                  <div className="random-movie-info">
                    <h2 className="random-movie-title">{movie.title}</h2>
                    <div className="random-movie-meta">
                      <span className="year">{movie.year}</span>
                      {movie.runtime && <span className="runtime">{movie.runtime} min</span>}
                      {movie.imdb_rating && <span className="imdb">IMDb: {movie.imdb_rating}</span>}
                    </div>
                    <div className="random-movie-genres">
                      {movie.genres?.split(',').map(g => g.trim()).join(' · ')}
                    </div>
                    {movie.directors && movie.directors !== 'Unknown' && (
                      <p className="random-movie-crew">
                        <strong>Director:</strong> {movie.directors.split(',').map(d => d.trim()).join(', ')}
                      </p>
                    )}
                    {movie.writers && movie.writers !== 'Unknown' && (
                      <p className="random-movie-crew">
                        <strong>Writers:</strong> {movie.writers.split(',').map(w => w.trim()).join(', ')}
                      </p>
                    )}
                    {movie.actors && movie.actors !== 'Unknown' && (
                      <p className="random-movie-crew">
                        <strong>Cast:</strong> {movie.actors.split(',').map(a => a.trim()).join(', ')}
                      </p>
                    )}
                    {movie.composers && movie.composers !== 'Unknown' && (
                      <p className="random-movie-crew">
                        <strong>Music:</strong> {movie.composers.split(',').map(c => c.trim()).join(', ')}
                      </p>
                    )}
                    {(movie.countries || movie.languages) && (
                      <p className="random-movie-crew random-movie-origin">
                        {movie.countries && movie.countries !== 'Unknown' && (
                          <span>{movie.countries.split(',').map(c => c.trim()).join(', ')}</span>
                        )}
                        {movie.countries && movie.languages && movie.countries !== 'Unknown' && movie.languages !== 'Unknown' && ' • '}
                        {movie.languages && movie.languages !== 'Unknown' && (
                          <span>{movie.languages.split(',').map(l => l.trim()).join(', ')}</span>
                        )}
                      </p>
                    )}
                    {movie.plot && movie.plot !== 'No synopsis available.' && movie.plot !== 'Sinopsis no disponible.' && (
                      <p className="random-movie-plot">{movie.plot}</p>
                    )}
                  </div>
                </div>

                <div className="random-rating-buttons">
                  {Object.values(ratingsConfig).map((opt) => (
                    <button
                      key={opt.label}
                      className="random-rating-btn"
                      onClick={() => handleRandomRating(opt.label, opt.score, movie)}
                      disabled={ratingLoading}
                      style={{ '--btn-color': opt.color }}
                    >
                      <Star size={20} fill={opt.color} color={opt.color} />
                      <span className="rating-label">{opt.label}</span>
                      <span className="rating-score">{opt.score}/10</span>
                    </button>
                  ))}
                </div>

                <button
                  className="random-skip-btn"
                  onClick={skipRandomMovie}
                  disabled={ratingLoading}
                >
                  <SkipForward size={18} />
                  Haven't seen it - Skip
                </button>
              </div>
            );
          })()}
        </div>
      ) : (
        <div className="empty-state premium">
          <div className="empty-icon">
            <Shuffle size={48} />
          </div>
          <h2>Ready to Rate?</h2>
          <p>Click "New Batch" to get a set of popular movies to rate.</p>
          <p className="hint">Optional: Set filters to narrow down by year or genre.</p>
          <button className="action-btn primary" onClick={startRandomSession}>
            <Shuffle size={18} />
            Start Rating
          </button>
        </div>
      )}
    </>
  );
}
