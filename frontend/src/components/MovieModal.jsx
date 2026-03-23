import React, { useState } from 'react';
import {
  Film,
  Brain,
  Star,
  RefreshCw,
  SkipForward,
  X,
  Sparkles,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

export default function MovieModal({ movie, details, prediction, predictionReasons, userRating, onClose, onSubmit, options, loading }) {
  const [showMoreDetails, setShowMoreDetails] = useState(false);

  if (!movie) return null;

  const displayMovie = details || movie;
  const posterUrl = displayMovie.poster_url;
  const hasValidPoster = posterUrl && !posterUrl.includes('placeholder');

  const hasWriters = displayMovie.writers && displayMovie.writers !== 'Unknown';
  const hasComposers = displayMovie.composers && displayMovie.composers !== 'Unknown';
  const hasOrigin = (displayMovie.countries && displayMovie.countries !== 'Unknown') ||
                    (displayMovie.languages && displayMovie.languages !== 'Unknown');
  const hasExtraDetails = hasWriters || hasComposers || hasOrigin;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content glass animate-in" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Movie Details</h2>
          <button className="close-btn" onClick={onClose}><X size={24} /></button>
        </div>

        <div className="modal-body">
          <div className="modal-movie-info">
            {hasValidPoster ? (
              <img src={posterUrl} alt={displayMovie.title} className="modal-poster" />
            ) : (
              <div className="modal-poster-placeholder">
                <Film size={32} />
                <span>{displayMovie.title?.charAt(0) || '?'}</span>
              </div>
            )}
            <div className="modal-movie-details">
              <h3>{displayMovie.title}</h3>
              <p className="movie-meta-modal">
                {displayMovie.year}
                {displayMovie.runtime && ` • ${displayMovie.runtime} min`}
                {displayMovie.imdb_rating && ` • IMDb: ${displayMovie.imdb_rating}/10`}
                {(() => {
                  if (!displayMovie.certificates) return null;
                  const certs = displayMovie.certificates.split(',');
                  const usaCert = certs.find(c => c.trim().startsWith('USA:'));
                  return usaCert ? ` • ${usaCert.replace('USA:', '').trim()}` : null;
                })()}
              </p>
              <p className="movie-genres">
                {displayMovie.genres?.split(',').map(g => g.trim()).join(' • ')}
              </p>
              {displayMovie.directors && displayMovie.directors !== 'Unknown' && (
                <p className="movie-crew">
                  <strong>Director:</strong> {displayMovie.directors.split(',').map(d => d.trim()).join(', ')}
                </p>
              )}
              {displayMovie.actors && displayMovie.actors !== 'Unknown' && (
                <p className="movie-crew">
                  <strong>Cast:</strong> {displayMovie.actors.split(',').map(a => a.trim()).join(', ')}
                </p>
              )}

              {hasExtraDetails && (
                <>
                  <div className={`movie-extra-details ${showMoreDetails ? 'expanded' : ''}`}>
                    {hasWriters && (
                      <p className="movie-crew">
                        <strong>Writers:</strong> {displayMovie.writers.split(',').map(w => w.trim()).join(', ')}
                      </p>
                    )}
                    {hasComposers && (
                      <p className="movie-crew">
                        <strong>Music:</strong> {displayMovie.composers.split(',').map(c => c.trim()).join(', ')}
                      </p>
                    )}
                    {hasOrigin && (
                      <p className="movie-crew movie-origin">
                        {displayMovie.countries && displayMovie.countries !== 'Unknown' && (
                          <span>{displayMovie.countries.split(',').map(c => c.trim()).join(', ')}</span>
                        )}
                        {displayMovie.countries && displayMovie.languages && displayMovie.countries !== 'Unknown' && displayMovie.languages !== 'Unknown' && ' • '}
                        {displayMovie.languages && displayMovie.languages !== 'Unknown' && (
                          <span>{displayMovie.languages.split(',').map(l => l.trim()).join(', ')}</span>
                        )}
                      </p>
                    )}
                  </div>
                  <button
                    className="show-more-btn"
                    onClick={() => setShowMoreDetails(!showMoreDetails)}
                  >
                    {showMoreDetails ? (
                      <>Show less <ChevronUp size={14} /></>
                    ) : (
                      <>Show more <ChevronDown size={14} /></>
                    )}
                  </button>
                </>
              )}
            </div>
          </div>

          {prediction !== null && (
            <div className="prediction-box-improved">
              <div className="pred-main">
                <div className="pred-left">
                  <Brain size={20} className="pred-icon" />
                  <span className="pred-label">Predicted Score</span>
                </div>
                <div className={`pred-score ${prediction >= 7 ? 'high' : prediction >= 5 ? 'mid' : 'low'}`}>
                  {prediction}<span className="pred-max">/10</span>
                </div>
              </div>
              {predictionReasons && predictionReasons.length > 0 && (
                <div className="pred-reasons">
                  <p className="pred-reasons-label">Why you'll like this:</p>
                  <div className="pred-reasons-tags">
                    {predictionReasons.map((reason, idx) => (
                      <span key={idx} className="pred-reason-tag">
                        <Sparkles size={10} />
                        {reason}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {displayMovie.plot && displayMovie.plot !== 'No synopsis available.' && (
            <div className="movie-plot">
              <p>{displayMovie.plot}</p>
            </div>
          )}

          <div className="rating-section">
            <h4>{userRating ? 'Update your rating:' : 'Rate this movie:'}</h4>
            <div className="rating-options-grid">
              {options.map((opt) => (
                <button
                  key={opt.label}
                  className={`rating-btn-compact glass${userRating?.label === opt.label ? ' active' : ''}`}
                  onClick={() => onSubmit(opt.label, opt.score)}
                  disabled={loading}
                  style={{ '--btn-color': opt.color }}
                >
                  <Star size={16} fill={opt.color} color={opt.color} />
                  <span className="rating-label">{opt.label}</span>
                  <span className="rating-score">{opt.score}/10</span>
                </button>
              ))}
            </div>
            <button
              className="skip-btn-modal"
              onClick={onClose}
              disabled={loading}
            >
              <SkipForward size={16} />
              <span>Haven't seen it (Skip)</span>
            </button>
          </div>
        </div>

        {loading && (
          <div className="loading-overlay">
            <RefreshCw size={24} className="spinning" />
            <span>Saving rating...</span>
          </div>
        )}
      </div>
    </div>
  );
}
