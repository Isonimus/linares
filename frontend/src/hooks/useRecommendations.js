import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API_BASE, PAGE_SIZE_REC } from '../constants';

export function useRecommendations(currentUser, isActive) {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedGenre, setSelectedGenre] = useState('');
  const [selectedFactor, setSelectedFactor] = useState('');
  const [recOffset, setRecOffset] = useState(0);
  const [hasMoreRecs, setHasMoreRecs] = useState(true);

  const fetchRecommendations = useCallback(async (isLoadMore = false) => {
    if (!currentUser) return;

    const currentOffset = isLoadMore ? recOffset + PAGE_SIZE_REC : 0;
    if (!isLoadMore) {
      setLoading(true);
      setRecOffset(0);
      setHasMoreRecs(true);
    }

    setError(null);
    try {
      let url = `${API_BASE}/recommendations/${currentUser.name}?limit=${PAGE_SIZE_REC}&offset=${currentOffset}`;
      if (selectedGenre) url += `&genre=${encodeURIComponent(selectedGenre)}`;
      if (selectedFactor) url += `&factor=${selectedFactor}`;
      const res = await axios.get(url);
      if (isLoadMore) {
        setRecommendations(prev => [...prev, ...res.data]);
        setRecOffset(currentOffset);
      } else {
        setRecommendations(res.data);
      }
      if (res.data.length < PAGE_SIZE_REC) {
        setHasMoreRecs(false);
      }
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error fetching recommendations", err);
      if (err.response?.status === 404) {
        setError("You don't have a trained model. Go to Settings to train it.");
      } else {
        setError("Error loading recommendations.");
      }
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  }, [currentUser, recOffset, selectedGenre, selectedFactor]);

  useEffect(() => {
    if (currentUser && isActive) {
      fetchRecommendations();
    }
  }, [currentUser, isActive, selectedGenre, selectedFactor]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    recommendations,
    loading,
    error,
    selectedGenre,
    setSelectedGenre,
    selectedFactor,
    setSelectedFactor,
    recOffset,
    hasMoreRecs,
    fetchRecommendations,
  };
}
