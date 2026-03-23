import React from 'react';
import { Film, Layers } from 'lucide-react';

export default function MovieCard({ movie, isSearchItem, onClick, onFindSimilar, harmonyScore, individualScores }) {
  const posterUrl = movie.poster_url;
  const hasValidPoster = posterUrl && !posterUrl.includes('placeholder');
  const score = harmonyScore ?? (!isSearchItem ? movie.predicted_score : null);
  const badgeClass = score >= 7 ? 'badge-high' : score >= 5 ? 'badge-mid' : 'badge-low';
  const hasBadgeColumn = score || movie.rating_label;

  return (
    <div className="movie-card glass" onClick={onClick}>
      {hasBadgeColumn && (
        <div className="badge-column">
          {score && (
            <>
              <div className={`prediction-badge ${badgeClass}`}>
                <div className="badge-score">{score}</div>
                <div className="badge-label">{harmonyScore ? 'Harmony' : 'Prediction'}</div>
              </div>
              {individualScores && Object.entries(individualScores).sort(([, a], [, b]) => b - a).map(([user, userScore]) => (
                <div key={user} className={`badge-user-score ${userScore >= 7 ? 'badge-high' : userScore >= 5 ? 'badge-mid' : 'badge-low'}`}>
                  <span className="badge-user-name">{user}</span>
                  <span className="badge-user-val">{userScore}</span>
                </div>
              ))}
            </>
          )}
          {movie.rating_label && (
            <div className="rated-badge">{movie.rating_label}</div>
          )}
        </div>
      )}
      {hasValidPoster ? (
        <img src={posterUrl} alt={movie.title} loading="lazy" />
      ) : (
        <div className="poster-placeholder">
          <Film size={32} />
          <span>{movie.title?.charAt(0) || '?'}</span>
        </div>
      )}
      {isSearchItem && onFindSimilar && (
        <button
          className="similar-btn"
          title="Find similar movies"
          onClick={(e) => { e.stopPropagation(); onFindSimilar(movie); }}
        >
          <Layers size={14} />
          <span>Find similar</span>
        </button>
      )}
      <div className="card-overlay">
        <div className="movie-title">{movie.title}</div>
        <div className="movie-meta">{movie.year} {movie.genres && `• ${movie.genres}`}</div>
      </div>
    </div>
  );
}
