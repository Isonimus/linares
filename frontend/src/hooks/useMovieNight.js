import { useState, useCallback } from 'react';
import axios from 'axios';
import { API_BASE, PAGE_SIZE_SHARED } from '../constants';

export function useMovieNight(currentUser) {
  const [selectedGuests, setSelectedGuests] = useState([]);
  const [sharedMovies, setSharedMovies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sharedOffset, setSharedOffset] = useState(0);
  const [hasMoreShared, setHasMoreShared] = useState(true);
  const [selectedFactorShared, setSelectedFactorShared] = useState('');

  const fetchSharedMovies = useCallback(async (isLoadMore = false) => {
    if (!currentUser || selectedGuests.length === 0) return;

    const currentOffset = isLoadMore ? sharedOffset + PAGE_SIZE_SHARED : 0;
    if (!isLoadMore) {
      setLoading(true);
      setSharedOffset(0);
      setHasMoreShared(true);
    }

    setError(null);
    try {
      const usersQuery = [currentUser, ...selectedGuests]
        .map(u => `users=${encodeURIComponent(u.name)}`)
        .join('&');
      let url = `${API_BASE}/recommend_shared?${usersQuery}&limit=${PAGE_SIZE_SHARED}&offset=${currentOffset}`;
      if (selectedFactorShared) url += `&factor=${selectedFactorShared}`;
      const res = await axios.get(url);
      if (isLoadMore) {
        setSharedMovies(prev => [...prev, ...res.data]);
        setSharedOffset(currentOffset);
      } else {
        setSharedMovies(res.data);
      }
      if (res.data.length < PAGE_SIZE_SHARED) {
        setHasMoreShared(false);
      }
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error fetching shared movies", err);
      setError(err.response?.data?.detail || "Error loading shared recommendations.");
      setSharedMovies([]);
    } finally {
      setLoading(false);
    }
  }, [currentUser, selectedGuests, sharedOffset, selectedFactorShared]);

  return {
    selectedGuests,
    setSelectedGuests,
    sharedMovies,
    setSharedMovies,
    loading,
    error,
    sharedOffset,
    hasMoreShared,
    selectedFactorShared,
    setSelectedFactorShared,
    fetchSharedMovies,
  };
}
