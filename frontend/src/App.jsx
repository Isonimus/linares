import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './App.css';
import {
  BarChart3,
  Search as SearchIcon,
  Settings,
  User as UserIcon,
  LayoutDashboard,
  Users,
  Shuffle,
  Plus,
} from 'lucide-react';

import { API_BASE } from './constants';
import { useRecommendations } from './hooks/useRecommendations';
import { useMovieNight } from './hooks/useMovieNight';
import { useStats } from './hooks/useStats';
import { useDiscover } from './hooks/useDiscover';

import MovieModal from './components/MovieModal';
import Notification from './components/Notification';
import RecommendationsTab from './components/RecommendationsTab';
import MovieNightTab from './components/MovieNightTab';
import SearchTab from './components/SearchTab';
import DiscoverTab from './components/DiscoverTab';
import StatsTab from './components/StatsTab';
import SettingsTab from './components/SettingsTab';

function App() {
  const [activeTab, setActiveTab] = useState('recommendations');
  const [currentUser, setCurrentUser] = useState(null);
  const [users, setUsers] = useState([]);
  const [genres, setGenres] = useState([]);
  const [ratingsConfig, setRatingsConfig] = useState({});

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [similarTo, setSimilarTo] = useState(null);
  const [similarMovies, setSimilarMovies] = useState([]);
  const [similarLoading, setSimilarLoading] = useState(false);

  // Modal state
  const [selectedMovie, setSelectedMovie] = useState(null);
  const [movieDetails, setMovieDetails] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [predictionReasons, setPredictionReasons] = useState([]);
  const [ratingLoading, setRatingLoading] = useState(false);

  // User management
  const [showNewUserModal, setShowNewUserModal] = useState(false);
  const [newUserName, setNewUserName] = useState('');
  const [retraining, setRetraining] = useState(false);

  // Notification
  const [notification, setNotification] = useState({ message: '', type: 'info', visible: false });

  const showNotification = useCallback((message, type = 'info') => {
    setNotification({ message, type, visible: true });
    setTimeout(() => {
      setNotification(prev => ({ ...prev, visible: false }));
    }, 4000);
  }, []);

  // Tab hooks
  const recsHook = useRecommendations(currentUser, activeTab === 'recommendations');
  const movieNightHook = useMovieNight(currentUser);
  const statsHook = useStats(currentUser, activeTab === 'stats' || activeTab === 'settings');
  const discoverHook = useDiscover(currentUser, showNotification);

  // Bootstrap
  useEffect(() => {
    fetchUsers();
    fetchRatingsConfig();
    fetchGenres();
  }, []);

  // Fetch random movies when switching to discover tab (if no movies loaded yet)
  useEffect(() => {
    if (activeTab === 'random' && currentUser && discoverHook.randomMovies.length === 0) {
      discoverHook.fetchRandomMovies();
    }
  }, [activeTab, currentUser]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchUsers = async () => {
    try {
      const res = await axios.get(`${API_BASE}/users`);
      setUsers(res.data);
      if (res.data.length > 0 && !currentUser) {
        setCurrentUser(res.data[0]);
      }
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error fetching users", err);
    }
  };

  const fetchRatingsConfig = async () => {
    try {
      const res = await axios.get(`${API_BASE}/config/ratings`);
      setRatingsConfig(res.data);
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error fetching ratings config", err);
    }
  };

  const fetchGenres = async () => {
    try {
      const res = await axios.get(`${API_BASE}/genres`);
      setGenres(res.data);
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error fetching genres", err);
    }
  };

  const handleFindSimilar = async (movie) => {
    const tconst = movie.tconst || movie.id;
    const title = movie.title || movie.l;
    setSimilarTo({ tconst, title });
    setSimilarMovies([]);
    setSimilarLoading(true);
    try {
      const params = { limit: 12 };
      if (currentUser) params.username = currentUser.name;
      const res = await axios.get(`${API_BASE}/similar/${tconst}`, { params });
      setSimilarMovies(res.data);
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error finding similar movies", err);
    } finally {
      setSimilarLoading(false);
    }
  };

  const handleSearch = async (e) => {
    const query = e.target.value;
    setSearchQuery(query);
    setSimilarTo(null);
    setSimilarMovies([]);
    if (query.length > 2) {
      try {
        let url = `${API_BASE}/search?q=${encodeURIComponent(query)}`;
        if (currentUser) url += `&username=${encodeURIComponent(currentUser.name)}`;
        const res = await axios.get(url);
        setSearchResults(res.data);
      } catch (err) {
        if (import.meta.env.DEV) console.error("Search error", err);
      }
    } else {
      setSearchResults([]);
    }
  };

  const handleCardClick = async (movie) => {
    setSelectedMovie(movie);
    setMovieDetails(null);
    setPrediction(null);
    setPredictionReasons([]);

    const tconst = movie.tconst || movie.id;
    try {
      const params = currentUser ? { username: currentUser.name } : {};
      const detailsRes = await axios.get(`${API_BASE}/movie/${tconst}`, { params });
      setMovieDetails(detailsRes.data);

      if (currentUser) {
        try {
          const predRes = await axios.get(`${API_BASE}/predict/${currentUser.name}/${tconst}`);
          if (typeof predRes.data === 'object' && predRes.data.prediction !== undefined) {
            setPrediction(predRes.data.prediction);
            setPredictionReasons(predRes.data.reasons || []);
          } else {
            setPrediction(predRes.data);
          }
        } catch {
          setPrediction(null);
          setPredictionReasons([]);
        }
      }
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error fetching movie details", err);
    }
  };

  const submitRating = async (label, score) => {
    if (!selectedMovie || !currentUser) return;
    setRatingLoading(true);
    const tconst = selectedMovie.tconst || selectedMovie.id;
    const isUpdate = !!(movieDetails?.rating_label);
    try {
      await axios.post(`${API_BASE}/rate`, null, {
        params: { username: currentUser.name, tconst, score, label }
      });
      showNotification(isUpdate ? `Rating updated to "${label}"` : `"${label}" saved!`, 'success');
      setSelectedMovie(null);
      setMovieDetails(null);
      setPrediction(null);
      setPredictionReasons([]);
      if (activeTab === 'recommendations') recsHook.fetchRecommendations();
      else if (activeTab === 'stats') statsHook.fetchStats();
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error submitting rating", err);
      showNotification("Error saving your rating.", "error");
    } finally {
      setRatingLoading(false);
    }
  };

  const createUser = async () => {
    if (!newUserName.trim()) return;
    try {
      const res = await axios.post(`${API_BASE}/users?name=${encodeURIComponent(newUserName.trim())}`);
      setUsers([...users, res.data]);
      setCurrentUser(res.data);
      setShowNewUserModal(false);
      setNewUserName('');
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error creating user", err);
      showNotification(err.response?.data?.detail || "Error creating user.", "error");
    }
  };

  const retrainModel = async () => {
    if (!currentUser) return;
    setRetraining(true);
    try {
      await axios.post(`${API_BASE}/retrain/${currentUser.name}`);
      showNotification("Model retrained successfully!", "success");
      statsHook.fetchStats();
      if (activeTab === 'recommendations') recsHook.fetchRecommendations();
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error retraining", err);
      showNotification(err.response?.data?.detail || "Error retraining the model.", "error");
    } finally {
      setRetraining(false);
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar glass">
        <div className="logo-block">
          <div className="logo">LINARES</div>
          <div className="logo-tagline">Latent Inference Network for<br/>Audiovisual Rating &amp; Entertainment Suggestion</div>
        </div>

        <nav>
          <div className={`nav-item ${activeTab === 'recommendations' ? 'active' : ''}`} onClick={() => setActiveTab('recommendations')}>
            <LayoutDashboard size={20} />
            <span>Recommendations</span>
          </div>
          <div className={`nav-item ${activeTab === 'cowatch' ? 'active' : ''}`} onClick={() => setActiveTab('cowatch')}>
            <Users size={20} />
            <span>Movie Night</span>
          </div>
          <div className={`nav-item ${activeTab === 'random' ? 'active' : ''}`} onClick={() => setActiveTab('random')}>
            <Shuffle size={20} />
            <span>Rate Random</span>
          </div>
          <div className={`nav-item ${activeTab === 'search' ? 'active' : ''}`} onClick={() => setActiveTab('search')}>
            <SearchIcon size={20} />
            <span>Search & Rate</span>
          </div>
          <div className={`nav-item ${activeTab === 'stats' ? 'active' : ''}`} onClick={() => setActiveTab('stats')}>
            <BarChart3 size={20} />
            <span>My Taste</span>
          </div>
          <div className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>
            <Settings size={20} />
            <span>Settings</span>
          </div>
        </nav>

        <div style={{ marginTop: 'auto' }}>
          <div className="user-badge glass" style={{ marginTop: '1rem' }}>
            <div style={{ background: 'var(--accent-secondary)', padding: '5px', borderRadius: '50%' }}>
              <UserIcon size={16} color="white" />
            </div>
            <select
              value={currentUser?.id || ''}
              onChange={(e) => setCurrentUser(users.find(u => u.id === parseInt(e.target.value)))}
              style={{ background: 'transparent', border: 'none', color: 'white', outline: 'none', cursor: 'pointer', flex: 1 }}
            >
              {users.map(u => <option key={u.id} value={u.id} style={{ color: 'black' }}>{u.name}</option>)}
            </select>
            <button
              onClick={() => setShowNewUserModal(true)}
              style={{ background: 'transparent', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer' }}
              title="New user"
            >
              <Plus size={18} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {activeTab === 'recommendations' && (
          <RecommendationsTab
            recommendations={recsHook.recommendations}
            loading={recsHook.loading}
            error={recsHook.error}
            genres={genres}
            selectedGenre={recsHook.selectedGenre}
            setSelectedGenre={recsHook.setSelectedGenre}
            selectedFactor={recsHook.selectedFactor}
            setSelectedFactor={recsHook.setSelectedFactor}
            hasMoreRecs={recsHook.hasMoreRecs}
            fetchRecommendations={recsHook.fetchRecommendations}
            onMovieClick={handleCardClick}
          />
        )}

        {activeTab === 'cowatch' && (
          <MovieNightTab
            users={users}
            currentUser={currentUser}
            selectedGuests={movieNightHook.selectedGuests}
            setSelectedGuests={movieNightHook.setSelectedGuests}
            sharedMovies={movieNightHook.sharedMovies}
            setSharedMovies={movieNightHook.setSharedMovies}
            loading={movieNightHook.loading}
            error={movieNightHook.error}
            selectedFactorShared={movieNightHook.selectedFactorShared}
            setSelectedFactorShared={movieNightHook.setSelectedFactorShared}
            fetchSharedMovies={movieNightHook.fetchSharedMovies}
            onMovieClick={handleCardClick}
          />
        )}

        {activeTab === 'search' && (
          <SearchTab
            searchQuery={searchQuery}
            searchResults={searchResults}
            handleSearch={handleSearch}
            onMovieClick={handleCardClick}
            onFindSimilar={handleFindSimilar}
            similarTo={similarTo}
            similarMovies={similarMovies}
            similarLoading={similarLoading}
          />
        )}

        {activeTab === 'random' && (
          <DiscoverTab
            randomMovies={discoverHook.randomMovies}
            randomIndex={discoverHook.randomIndex}
            randomFilterYear={discoverHook.randomFilterYear}
            setRandomFilterYear={discoverHook.setRandomFilterYear}
            randomFilterGenre={discoverHook.randomFilterGenre}
            setRandomFilterGenre={discoverHook.setRandomFilterGenre}
            randomSessionStats={discoverHook.randomSessionStats}
            loading={discoverHook.loading}
            error={discoverHook.error}
            ratingLoading={discoverHook.ratingLoading}
            ratingsConfig={ratingsConfig}
            genres={genres}
            startRandomSession={discoverHook.startRandomSession}
            handleRandomRating={discoverHook.handleRandomRating}
            skipRandomMovie={discoverHook.skipRandomMovie}
          />
        )}

        {activeTab === 'stats' && (
          <StatsTab
            stats={statsHook.stats}
            insights={statsHook.insights}
            loading={statsHook.loading}
            deleteRating={statsHook.deleteRating}
            onSearchClick={() => setActiveTab('search')}
          />
        )}

        {activeTab === 'settings' && (
          <SettingsTab
            currentUser={currentUser}
            stats={statsHook.stats}
            insights={statsHook.insights}
            ratingsConfig={ratingsConfig}
            retraining={retraining}
            retrainModel={retrainModel}
            onNewUser={() => setShowNewUserModal(true)}
          />
        )}
      </main>

      <Notification
        message={notification.message}
        type={notification.type}
        visible={notification.visible}
        onClose={() => setNotification(prev => ({ ...prev, visible: false }))}
      />

      {selectedMovie && (
        <MovieModal
          movie={selectedMovie}
          details={movieDetails}
          prediction={prediction}
          predictionReasons={predictionReasons}
          userRating={movieDetails?.rating_label ? { label: movieDetails.rating_label, score: movieDetails.rating_score } : null}
          onClose={() => setSelectedMovie(null)}
          onSubmit={submitRating}
          options={Object.values(ratingsConfig)}
          loading={ratingLoading}
        />
      )}

      {showNewUserModal && (
        <div className="modal-overlay" onClick={() => setShowNewUserModal(false)}>
          <div className="modal-content glass animate-in" onClick={e => e.stopPropagation()} style={{ maxWidth: '400px' }}>
            <div className="modal-header">
              <h2>New User</h2>
              <button className="close-btn" onClick={() => setShowNewUserModal(false)}>&times;</button>
            </div>
            <div className="modal-body">
              <input
                type="text"
                className="input-field"
                placeholder="Username"
                value={newUserName}
                onChange={(e) => setNewUserName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && createUser()}
                autoFocus
              />
              <button className="action-btn primary" onClick={createUser} style={{ marginTop: '1rem', width: '100%' }}>
                Create user
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
