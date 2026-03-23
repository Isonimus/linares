import React from 'react';
import { Brain, Film, Target, Zap, Star, Sparkles, RefreshCw, Plus, User as UserIcon } from 'lucide-react';

export default function SettingsTab({
  currentUser,
  stats,
  insights,
  ratingsConfig,
  retraining,
  retrainModel,
  onNewUser,
}) {
  return (
    <>
      <header>
        <h1>Settings</h1>
        <p className="header-subtitle">Manage your profile and AI model</p>
      </header>

      <div className="settings-premium-container animate-in">
        {/* User Profile Section */}
        <div className="settings-card glass">
          <div className="settings-card-header">
            <div className="settings-card-icon">
              <UserIcon size={24} />
            </div>
            <div className="settings-card-title">
              <h3>User Profile</h3>
              <p>Manage your account</p>
            </div>
          </div>
          <div className="settings-card-body">
            <div className="current-user-display">
              <div className="user-avatar-large">
                <span>{currentUser?.name?.charAt(0)?.toUpperCase() || '?'}</span>
              </div>
              <div className="user-details">
                <span className="user-name-large">{currentUser?.name || 'No user selected'}</span>
                <span className="user-meta">
                  {stats ? `${stats.total_ratings} movies rated` : 'Loading...'}
                </span>
              </div>
            </div>
            <div className="user-actions">
              <button className="action-btn secondary" onClick={onNewUser}>
                <Plus size={18} />
                New Profile
              </button>
            </div>
          </div>
        </div>

        {/* AI Model Section */}
        <div className="settings-card glass highlight">
          <div className="settings-card-header">
            <div className="settings-card-icon glow">
              <Brain size={24} />
            </div>
            <div className="settings-card-title">
              <h3>AI Model</h3>
              <p>Your personalized recommendation engine</p>
            </div>
            <div className={`model-status-badge ${stats?.has_model ? 'active' : 'inactive'}`}>
              {stats?.has_model ? 'Trained' : 'Not Trained'}
            </div>
          </div>
          <div className="settings-card-body">
            <div className="model-info-grid">
              <div className="model-info-item">
                <Film size={18} />
                <span className="model-info-value">{stats?.total_ratings || 0}</span>
                <span className="model-info-label">Training Samples</span>
              </div>
              <div className="model-info-item">
                <Target size={18} />
                <span className="model-info-value">{stats?.total_ratings >= 50 ? 'Good' : 'Low'}</span>
                <span className="model-info-label">Data Quality</span>
              </div>
              <div className="model-info-item">
                <Zap size={18} />
                <span className="model-info-value">CatBoost</span>
                <span className="model-info-label">Algorithm</span>
              </div>
            </div>

            {stats && stats.total_ratings < 50 && (
              <div className="model-warning">
                <Sparkles size={16} />
                <span>Rate at least 50 movies for optimal predictions. You need {50 - stats.total_ratings} more.</span>
              </div>
            )}

            {insights && insights.what_matters_most && (
              <div className="model-insight-preview">
                <div className="insight-preview-label">Current Model Insights:</div>
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

            <button
              className="train-model-btn"
              onClick={retrainModel}
              disabled={retraining || !currentUser}
            >
              {retraining ? (
                <>
                  <RefreshCw size={20} className="spinning" />
                  <span>Training Model...</span>
                  <span className="train-hint">This may take a minute</span>
                </>
              ) : (
                <>
                  <Zap size={20} />
                  <span>Retrain AI Model</span>
                  <span className="train-hint">Incorporate your latest ratings</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Rating Scale Section */}
        <div className="settings-card glass">
          <div className="settings-card-header">
            <div className="settings-card-icon">
              <Star size={24} />
            </div>
            <div className="settings-card-title">
              <h3>Rating Scale</h3>
              <p>How your ratings translate to scores</p>
            </div>
          </div>
          <div className="settings-card-body">
            <div className="rating-scale-grid">
              {Object.values(ratingsConfig).map((opt) => (
                <div key={opt.label} className="rating-scale-card">
                  <Star size={24} fill={opt.color} color={opt.color} />
                  <span className="scale-label">{opt.label}</span>
                  <span className="scale-score">{opt.score}/10</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* About Section */}
        <div className="settings-card glass">
          <div className="settings-card-header">
            <div className="settings-card-icon">
              <Sparkles size={24} />
            </div>
            <div className="settings-card-title">
              <h3>About LINARES</h3>
              <p>Latent Inference Network for Audiovisual Rating and Entertainment Suggestion</p>
            </div>
          </div>
          <div className="settings-card-body">
            <div className="about-content">
              <p>
                LINARES is a private, local movie recommendation engine that learns your unique taste
                through machine learning. You rate movies you've seen; LINARES trains a personalized
                model on your ratings and predicts exactly how much you'll enjoy anything else.
                It gets meaningfully better the more you use it — and all data stays on your machine.
              </p>
              <p className="about-namesake">
                Named after <strong>Félix Linares</strong>, the legendary Basque film critic and
                presenter of <em>La Noche de...</em>, whose passion for cinema inspired this project.
              </p>
              <div className="tech-stack">
                <span className="tech-tag">CatBoost ML</span>
                <span className="tech-tag">NLP Plot Embeddings</span>
                <span className="tech-tag">Target Encoding</span>
                <span className="tech-tag">Similarity Search</span>
                <span className="tech-tag">TMDB</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
