import { useState, useCallback } from 'react';
import axios from 'axios';
import { API_BASE } from '../constants';

export function useDiscover(currentUser, showNotification) {
  const [randomMovies, setRandomMovies] = useState([]);
  const [randomIndex, setRandomIndex] = useState(0);
  const [randomFilterYear, setRandomFilterYear] = useState('');
  const [randomFilterGenre, setRandomFilterGenre] = useState('');
  const [randomSessionStats, setRandomSessionStats] = useState({ rated: 0, skipped: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [ratingLoading, setRatingLoading] = useState(false);

  const fetchRandomMovies = useCallback(async () => {
    if (!currentUser) return;
    setLoading(true);
    setError(null);
    try {
      let url = `${API_BASE}/random/${currentUser.name}?limit=20`;
      if (randomFilterYear) url += `&year=${randomFilterYear}`;
      if (randomFilterGenre) url += `&genre=${encodeURIComponent(randomFilterGenre)}`;
      const res = await axios.get(url);
      setRandomMovies(res.data);
      setRandomIndex(0);
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error fetching random movies", err);
      setError("Error loading movies. Try different filters.");
      setRandomMovies([]);
    } finally {
      setLoading(false);
    }
  }, [currentUser, randomFilterYear, randomFilterGenre]);

  const moveToNextRandomMovie = useCallback(() => {
    setRandomIndex(prev => {
      if (prev < randomMovies.length - 1) {
        return prev + 1;
      }
      fetchRandomMovies();
      return prev;
    });
  }, [randomMovies.length, fetchRandomMovies]);

  const handleRandomRating = useCallback(async (label, score, movie) => {
    if (!movie || !currentUser) return;
    setRatingLoading(true);
    try {
      await axios.post(`${API_BASE}/rate`, null, {
        params: { username: currentUser.name, tconst: movie.tconst, score, label }
      });
      setRandomSessionStats(prev => ({ ...prev, rated: prev.rated + 1 }));
      moveToNextRandomMovie();
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error submitting rating", err);
      showNotification("Error saving rating.", "error");
    } finally {
      setRatingLoading(false);
    }
  }, [currentUser, moveToNextRandomMovie, showNotification]);

  const skipRandomMovie = useCallback(() => {
    setRandomSessionStats(prev => ({ ...prev, skipped: prev.skipped + 1 }));
    moveToNextRandomMovie();
  }, [moveToNextRandomMovie]);

  const startRandomSession = useCallback(() => {
    setRandomSessionStats({ rated: 0, skipped: 0 });
    fetchRandomMovies();
  }, [fetchRandomMovies]);

  return {
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
    fetchRandomMovies,
    handleRandomRating,
    skipRandomMovie,
    startRandomSession,
  };
}
