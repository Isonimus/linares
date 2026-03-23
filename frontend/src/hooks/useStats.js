import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API_BASE } from '../constants';

export function useStats(currentUser, isActive) {
  const [stats, setStats] = useState(null);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchStats = useCallback(async () => {
    if (!currentUser) return;
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/stats/${currentUser.name}`);
      setStats(res.data);
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error fetching stats", err);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [currentUser]);

  const fetchInsights = useCallback(async () => {
    if (!currentUser) return;
    try {
      const res = await axios.get(`${API_BASE}/insights/${currentUser.name}`);
      setInsights(res.data);
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error fetching insights", err);
      setInsights(null);
    }
  }, [currentUser]);

  const deleteRating = useCallback(async (tconst) => {
    if (!currentUser) return;
    try {
      await axios.delete(`${API_BASE}/ratings/${currentUser.name}/${tconst}`);
      fetchStats();
    } catch (err) {
      if (import.meta.env.DEV) console.error("Error deleting rating", err);
    }
  }, [currentUser, fetchStats]);

  useEffect(() => {
    if (currentUser && isActive) {
      fetchStats();
      fetchInsights();
    }
  }, [currentUser, isActive]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    stats,
    insights,
    loading,
    fetchStats,
    fetchInsights,
    deleteRating,
  };
}
