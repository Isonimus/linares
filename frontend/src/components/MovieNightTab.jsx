import React from 'react';
import { Film, RefreshCw, Users, Sparkles, CheckCircle } from 'lucide-react';
import MovieCard from './MovieCard';
import FactorPills from './FactorPills';

export default function MovieNightTab({
  users,
  currentUser,
  selectedGuests,
  setSelectedGuests,
  setSharedMovies,
  sharedMovies,
  loading,
  error,
  selectedFactorShared,
  setSelectedFactorShared,
  fetchSharedMovies,
  onMovieClick,
}) {
  return (
    <>
      <header>
        <h1>Movie Night</h1>
        <p className="header-subtitle">Find movies everyone will enjoy based on your combined tastes.</p>
      </header>

      <div className="cowatch-controls glass" style={{ marginBottom: '2rem', padding: '1.5rem', borderRadius: '12px' }}>
        <div className="guest-selector" style={{ marginBottom: '1rem' }}>
          <h3 style={{ marginTop: 0, marginBottom: '0.5rem', fontSize: '1rem', color: 'var(--text-secondary)' }}>Select Guests:</h3>
          <div className="guest-list" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {users.filter(u => u.name !== currentUser?.name).map(user => {
              const isSelected = selectedGuests.some(g => g.name === user.name);
              return (
                <label key={user.name} className={`guest-checkbox ${isSelected ? 'selected' : ''}`} style={{
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  padding: '0.5rem 1rem', borderRadius: '20px',
                  background: isSelected ? 'rgba(99, 102, 241, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                  border: `1px solid ${isSelected ? 'var(--accent-primary)' : 'rgba(255,255,255,0.1)'}`,
                  cursor: 'pointer', transition: 'all 0.2s ease'
                }}>
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedGuests([...selectedGuests, user]);
                      } else {
                        setSelectedGuests(selectedGuests.filter(g => g.name !== user.name));
                      }
                      setSharedMovies([]);
                    }}
                    style={{ display: 'none' }}
                  />
                  <div style={{
                    width: '16px', height: '16px', borderRadius: '4px',
                    border: `1px solid ${isSelected ? 'var(--accent-primary)' : 'rgba(255,255,255,0.3)'}`,
                    background: isSelected ? 'var(--accent-primary)' : 'transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    {isSelected && <CheckCircle size={12} color="white" />}
                  </div>
                  {user.name}
                </label>
              );
            })}
            {users.length <= 1 && (
              <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic', margin: 0 }}>
                You need to create at least one other profile first.
              </p>
            )}
          </div>
        </div>
        <FactorPills value={selectedFactorShared} onChange={setSelectedFactorShared} />
        <button
          className="action-btn primary"
          onClick={() => fetchSharedMovies()}
          disabled={selectedGuests.length === 0 || loading}
          style={{ width: '100%', justifyContent: 'center', marginTop: '1rem' }}
        >
          <Sparkles size={18} />
          Find Shared Movies
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="movie-grid animate-in">
        {loading ? (
          <div className="loading-container" style={{ gridColumn: '1 / -1' }}>
            <RefreshCw size={32} className="spinning" />
            <p>Calculating harmony scores...</p>
          </div>
        ) : sharedMovies.length > 0 ? (
          sharedMovies.map((movie) => (
            <MovieCard
              key={movie.tconst}
              movie={movie}
              onClick={() => onMovieClick(movie)}
              harmonyScore={movie.predicted_score}
              individualScores={movie.individual_scores}
            />
          ))
        ) : selectedGuests.length > 0 && !error ? (
          <div className="empty-state" style={{ gridColumn: '1 / -1' }}>
            <Film size={48} />
            <p>Click "Find Shared Movies" to see recommendations.</p>
          </div>
        ) : (
          <div className="empty-state" style={{ gridColumn: '1 / -1' }}>
            <Users size={48} />
            <p>Select at least one guest to get shared recommendations.</p>
          </div>
        )}
      </div>
    </>
  );
}
