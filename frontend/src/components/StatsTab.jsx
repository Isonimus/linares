import React from 'react';
import {
  BarChart3, Film, Star, Brain, Sparkles, TrendingUp, Target, Heart,
  BookOpen, Calendar, Clapperboard, Users, PenTool, Music, Tag,
  Globe, Shield, Clock, RefreshCw, Search as SearchIcon, Trash2
} from 'lucide-react';

export default function StatsTab({ stats, insights, loading, deleteRating, onSearchClick }) {
  return (
    <>
      <header>
        <h1>My Taste</h1>
        <p className="header-subtitle">Your personalized movie taste analysis</p>
      </header>

      {loading ? (
        <div className="loading-container">
          <RefreshCw size={32} className="spinning" />
          <p>Analyzing your taste profile...</p>
        </div>
      ) : stats ? (
        <div className="stats-premium-container animate-in">
          {/* Hero Stats Row */}
          <div className="stats-hero-row">
            <div className="hero-stat-card glass">
              <div className="hero-stat-icon">
                <Film size={28} />
              </div>
              <div className="hero-stat-content">
                <div className="hero-stat-value">{stats.total_ratings}</div>
                <div className="hero-stat-label">Movies Rated</div>
              </div>
            </div>
            <div className="hero-stat-card glass">
              <div className="hero-stat-icon accent-secondary">
                <Star size={28} />
              </div>
              <div className="hero-stat-content">
                <div className="hero-stat-value">{stats.average_score}</div>
                <div className="hero-stat-label">Average Score</div>
              </div>
            </div>
            <div className="hero-stat-card glass">
              <div className="hero-stat-icon accent-tertiary">
                <Brain size={28} />
              </div>
              <div className="hero-stat-content">
                <div className="hero-stat-value">{stats.has_model ? 'Active' : 'None'}</div>
                <div className="hero-stat-label">AI Model</div>
              </div>
            </div>
          </div>

          {/* ML Insights Section */}
          {insights && (
            <div className="insights-section">
              {insights.what_matters_most && (
                <div className="insight-card glass premium-gradient full-width">
                  <div className="insight-header">
                    <Sparkles size={22} />
                    <h3>What Drives Your Taste</h3>
                  </div>
                  <ul className="insight-list">
                    {(Array.isArray(insights.what_matters_most)
                      ? insights.what_matters_most
                      : [insights.what_matters_most]
                    ).map((insight, i) => (
                      <li key={i}>{insight}</li>
                    ))}
                  </ul>
                </div>
              )}

              {insights.underlying_patterns?.patterns?.length > 0 && (
                <div className="insight-card glass full-width underlying-patterns-card">
                  <div className="insight-header">
                    <TrendingUp size={20} />
                    <h3>Patterns in Your Data</h3>
                  </div>
                  <p className="patterns-note">Direct correlations that explain your preferences:</p>
                  <div className="patterns-list">
                    {insights.underlying_patterns.patterns.map((p, i) => (
                      <div key={i} className="pattern-item">
                        <span className="pattern-description">{p.description}</span>
                        {p.detail && <span className="pattern-detail">{p.detail}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="insights-grid">
                {insights.top_features && insights.top_features.length > 0 && (
                  <div className="insight-card glass">
                    <div className="insight-header">
                      <Target size={20} />
                      <h3>Prediction Factors</h3>
                    </div>
                    <div className="feature-list">
                      {insights.top_features.slice(0, 6).map((f, i) => (
                        <div key={i} className="feature-item">
                          <span className="feature-rank">#{i + 1}</span>
                          <span className="feature-name">{f.feature}</span>
                          <div className="feature-bar-container">
                            <div className="feature-bar" style={{ width: `${Math.min(100, f.importance)}%` }} />
                          </div>
                          <span className="feature-pct">{Math.round(f.importance)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {insights.genre_preferences && (
                  <div className="insight-card glass">
                    <div className="insight-header">
                      <Heart size={20} />
                      <h3>Genre Taste</h3>
                    </div>
                    <div className="genre-taste-grid">
                      {insights.genre_preferences.favorites && insights.genre_preferences.favorites.length > 0 && (
                        <div className="taste-column favorites">
                          <div className="taste-label">
                            <TrendingUp size={14} />
                            <span>Love</span>
                          </div>
                          {insights.genre_preferences.favorites.map((g, i) => (
                            <div key={i} className="taste-tag favorite">{g.genre}</div>
                          ))}
                        </div>
                      )}
                      {insights.genre_preferences.least_favorites && insights.genre_preferences.least_favorites.length > 0 && (
                        <div className="taste-column least-favorites">
                          <div className="taste-label">
                            <span>Meh</span>
                          </div>
                          {insights.genre_preferences.least_favorites.map((g, i) => (
                            <div key={i} className="taste-tag least-favorite">{g.genre}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {insights.plot_themes && insights.plot_themes.length > 0 && (
                  <div className="insight-card glass">
                    <div className="insight-header">
                      <BookOpen size={20} />
                      <h3>Story Themes You Love</h3>
                    </div>
                    <div className="plot-themes-grid">
                      {insights.plot_themes.map((t, i) => (
                        <div key={i} className="theme-tag">{t.theme}</div>
                      ))}
                    </div>
                  </div>
                )}

                {insights.era_preferences && insights.era_preferences.length > 0 && (
                  <div className="insight-card glass">
                    <div className="insight-header">
                      <Calendar size={20} />
                      <h3>Favorite Eras</h3>
                    </div>
                    <div className="era-grid">
                      {insights.era_preferences.map((era, i) => (
                        <div key={i} className="era-item">
                          <div className="era-decade">{era.decade}</div>
                          <div className="era-stats">
                            <span className="era-count">{era.count} films</span>
                            <span className="era-rating">{era.avg_score}/10</span>
                          </div>
                          <div className="era-bar-bg">
                            <div className="era-bar-fill" style={{ width: `${(era.avg_score / 10) * 100}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Favorite People Row */}
              <div className="people-insights-row">
                {insights.favorite_directors && insights.favorite_directors.length > 0 && (
                  <div className="insight-card glass compact">
                    <div className="insight-header">
                      <Clapperboard size={18} />
                      <h3>Directors</h3>
                    </div>
                    <div className="person-grid">
                      {insights.favorite_directors.slice(0, 4).map((d, i) => (
                        <div key={i} className="person-item">
                          <div className="person-avatar director"><span>{d.name.charAt(0)}</span></div>
                          <div className="person-info">
                            <span className="person-name">{d.name}</span>
                            <span className="person-meta">{d.avg_score}/10{d.count > 0 && ` · ${d.count} films`}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {insights.favorite_actors && insights.favorite_actors.length > 0 && (
                  <div className="insight-card glass compact">
                    <div className="insight-header">
                      <Users size={18} />
                      <h3>Actors</h3>
                    </div>
                    <div className="person-grid">
                      {insights.favorite_actors.slice(0, 4).map((a, i) => (
                        <div key={i} className="person-item">
                          <div className="person-avatar actor"><span>{a.name.charAt(0)}</span></div>
                          <div className="person-info">
                            <span className="person-name">{a.name}</span>
                            <span className="person-meta">{a.avg_score}/10{a.count > 0 && ` · ${a.count} films`}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {insights.favorite_writers && insights.favorite_writers.length > 0 && (
                  <div className="insight-card glass compact">
                    <div className="insight-header">
                      <PenTool size={18} />
                      <h3>Writers</h3>
                    </div>
                    <div className="person-grid">
                      {insights.favorite_writers.slice(0, 4).map((w, i) => (
                        <div key={i} className="person-item">
                          <div className="person-avatar writer"><span>{w.name.charAt(0)}</span></div>
                          <div className="person-info">
                            <span className="person-name">{w.name}</span>
                            <span className="person-meta">{w.avg_score}/10{w.count > 0 && ` · ${w.count} films`}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {insights.favorite_composers && insights.favorite_composers.length > 0 && (
                  <div className="insight-card glass compact">
                    <div className="insight-header">
                      <Music size={18} />
                      <h3>Composers</h3>
                    </div>
                    <div className="person-grid">
                      {insights.favorite_composers.slice(0, 4).map((c, i) => (
                        <div key={i} className="person-item">
                          <div className="person-avatar composer"><span>{c.name.charAt(0)}</span></div>
                          <div className="person-info">
                            <span className="person-name">{c.name}</span>
                            <span className="person-meta">{c.avg_score}/10{c.count > 0 && ` · ${c.count} films`}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Advanced Insights Row */}
              <div className="advanced-insights-row">
                {insights.keyword_preferences?.favorites?.length > 0 && (
                  <div className="insight-card glass">
                    <div className="insight-header">
                      <Tag size={20} />
                      <h3>Favorite Tags</h3>
                    </div>
                    <div className="keyword-grid">
                      {insights.keyword_preferences.favorites.slice(0, 6).map((k, i) => (
                        <div key={i} className="keyword-item">
                          <span className="keyword-name">{k.keyword.replace(/-/g, ' ')}</span>
                          <span className="keyword-score">{k.avg_score}/10</span>
                        </div>
                      ))}
                    </div>
                    {insights.keyword_preferences.avoided?.length > 0 && (
                      <div className="keyword-avoided">
                        <span className="avoided-label">Less enjoyed:</span>
                        {insights.keyword_preferences.avoided.slice(0, 3).map((k, i) => (
                          <span key={i} className="avoided-tag">{k.keyword.replace(/-/g, ' ')}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {insights.popularity_preference && insights.popularity_preference.preference !== 'insufficient_data' && (
                  <div className="insight-card glass">
                    <div className="insight-header">
                      <TrendingUp size={20} />
                      <h3>Popularity Profile</h3>
                    </div>
                    <div className="popularity-content">
                      <div className="popularity-badge" data-type={insights.popularity_preference.preference}>
                        {insights.popularity_preference.preference === 'hidden_gem_hunter' && 'Hidden Gem Hunter'}
                        {insights.popularity_preference.preference === 'blockbuster_fan' && 'Blockbuster Fan'}
                        {insights.popularity_preference.preference === 'balanced' && 'Balanced Viewer'}
                        {insights.popularity_preference.preference === 'contrarian' && 'Against the Grain'}
                        {insights.popularity_preference.preference === 'quality_aligns_with_popularity' && 'Crowd Aligned'}
                      </div>
                      <p className="popularity-summary">{insights.popularity_preference.summary}</p>
                      {insights.popularity_preference.by_popularity && (
                        <div className="popularity-breakdown">
                          {insights.popularity_preference.by_popularity.blockbusters && (
                            <div className="pop-stat">
                              <span className="pop-label">Blockbusters</span>
                              <span className="pop-value">{insights.popularity_preference.by_popularity.blockbusters.avg_score}/10</span>
                              <span className="pop-count">({insights.popularity_preference.by_popularity.blockbusters.count})</span>
                            </div>
                          )}
                          {insights.popularity_preference.by_popularity.obscure && (
                            <div className="pop-stat">
                              <span className="pop-label">Hidden Gems</span>
                              <span className="pop-value">{insights.popularity_preference.by_popularity.obscure.avg_score}/10</span>
                              <span className="pop-count">({insights.popularity_preference.by_popularity.obscure.count})</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {(insights.international_taste?.countries?.length > 0 || insights.international_taste?.languages?.length > 0) && (
                  <div className="insight-card glass">
                    <div className="insight-header">
                      <Globe size={20} />
                      <h3>International Taste</h3>
                    </div>
                    <div className="international-content">
                      {insights.international_taste.countries?.length > 0 && (
                        <div className="intl-section">
                          <span className="intl-label">Top Countries</span>
                          <div className="intl-items">
                            {insights.international_taste.countries.slice(0, 4).map((c, i) => (
                              <div key={i} className="intl-item">
                                <span className="intl-name">{c.country}</span>
                                <span className="intl-score">{c.avg_score}/10</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {insights.international_taste.languages?.length > 0 && (
                        <div className="intl-section">
                          <span className="intl-label">Top Languages</span>
                          <div className="intl-items">
                            {insights.international_taste.languages.slice(0, 4).map((l, i) => (
                              <div key={i} className="intl-item">
                                <span className="intl-name">{l.language}</span>
                                <span className="intl-score">{l.avg_score}/10</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {insights.maturity_preference?.ratings?.length > 0 && (
                  <div className="insight-card glass">
                    <div className="insight-header">
                      <Shield size={20} />
                      <h3>Content Preference</h3>
                    </div>
                    <div className="maturity-content">
                      <div className="maturity-badge" data-type={insights.maturity_preference.preference}>
                        {insights.maturity_preference.preference === 'mature' && 'Mature Content'}
                        {insights.maturity_preference.preference === 'balanced' && 'Balanced'}
                        {insights.maturity_preference.preference === 'family_friendly' && 'Family Friendly'}
                        {insights.maturity_preference.preference === 'adult' && 'Adult Only'}
                        {insights.maturity_preference.preference === 'varied' && 'All Ratings'}
                      </div>
                      <p className="maturity-summary">{insights.maturity_preference.summary}</p>
                      <div className="maturity-bars">
                        {insights.maturity_preference.ratings.map((r, i) => (
                          <div key={i} className="maturity-bar">
                            <span className="maturity-label">{r.rating}</span>
                            <div className="maturity-bar-bg">
                              <div className="maturity-bar-fill" style={{ width: `${(r.avg_score / 10) * 100}%` }} />
                            </div>
                            <span className="maturity-score">{r.avg_score}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Traditional Stats */}
          <div className="stats-traditional-row">
            {stats.score_distribution && (
              <div className="insight-card glass wide">
                <div className="insight-header">
                  <BarChart3 size={20} />
                  <h3>Rating Distribution</h3>
                </div>
                <div className="distribution-chart">
                  {stats.score_distribution.map((d) => (
                    <div key={d.range} className="dist-column">
                      <div className="dist-bar-wrapper">
                        <div
                          className="dist-bar"
                          style={{ height: `${Math.max(8, (stats.total_ratings > 0 ? (d.count / stats.total_ratings) * 180 : 0))}px` }}
                        >
                          <span className="dist-count">{d.count}</span>
                        </div>
                      </div>
                      <span className="dist-label">{d.range}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {stats.genre_stats.length > 0 && (
              <div className="insight-card glass">
                <div className="insight-header">
                  <TrendingUp size={20} />
                  <h3>Top Genres by Rating</h3>
                </div>
                <div className="genre-ranking">
                  {stats.genre_stats.slice(0, 6).map((g, i) => (
                    <div key={g.genre} className="genre-rank-item">
                      <span className="genre-position">{i + 1}</span>
                      <div className="genre-rank-info">
                        <span className="genre-rank-name">{g.genre}</span>
                        <div className="genre-rank-bar-bg">
                          <div className="genre-rank-bar" style={{ width: `${(g.avg_score / 10) * 100}%` }} />
                        </div>
                      </div>
                      <span className="genre-rank-score">{g.avg_score}</span>
                      <span className="genre-rank-count">({g.count})</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {stats.recent_ratings.length > 0 && (
            <div className="insight-card glass full-width">
              <div className="insight-header">
                <Clock size={20} />
                <h3>Recent Activity</h3>
              </div>
              <div className="recent-activity-grid">
                {stats.recent_ratings.map((r) => (
                  <div key={r.tconst} className="recent-activity-item">
                    {r.poster_url ? (
                      <img src={r.poster_url} alt={r.title} className="recent-poster-small" />
                    ) : (
                      <div className="recent-poster-placeholder-small">
                        <Film size={16} />
                      </div>
                    )}
                    <div className="recent-activity-info">
                      <span className="recent-activity-title">{r.title}</span>
                      <span className="recent-activity-meta">{r.year}</span>
                    </div>
                    <div className={`recent-activity-score ${r.rating_score >= 7 ? 'high' : r.rating_score >= 5 ? 'mid' : 'low'}`}>
                      {r.rating_score}
                    </div>
                    <button className="delete-btn-small" onClick={() => deleteRating(r.tconst)} title="Delete rating">
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="empty-state premium">
          <div className="empty-icon">
            <BarChart3 size={48} />
          </div>
          <h2>No Stats Yet</h2>
          <p>Start rating movies to unlock your personalized taste analysis.</p>
          <button className="action-btn primary" onClick={onSearchClick}>
            <SearchIcon size={18} />
            Start Rating
          </button>
        </div>
      )}
    </>
  );
}
