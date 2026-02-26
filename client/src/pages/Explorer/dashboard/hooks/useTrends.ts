/**
 * Hook for fetching time-series trend data from dashboard snapshots.
 */

import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../../../auth/useAuth';
import type { ScoreTrendData, TrendData } from '../types';
import { fetchScoreTrends, fetchTrends } from '../api/dashboardApi';

export function useTrends() {
    const [trends, setTrends] = useState<TrendData | null>(null);
    const [scoreTrends, setScoreTrends] = useState<ScoreTrendData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const { getApiAccessToken } = useAuth();
    const abortRef = useRef<AbortController | null>(null);

    useEffect(() => {
        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;

        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const token = await getApiAccessToken();
                if (!token || controller.signal.aborted) return;

                const [trendsResult, scoreResult] = await Promise.all([
                    fetchTrends(token, controller.signal),
                    fetchScoreTrends(token, controller.signal),
                ]);

                if (!controller.signal.aborted) {
                    setTrends(trendsResult);
                    setScoreTrends(scoreResult);
                    setLoading(false);
                }
            } catch (err: any) {
                if (err?.name === 'AbortError') return;
                setError(err?.message || 'Failed to load trend data');
                setLoading(false);
            }
        };

        fetchData();
        return () => controller.abort();
    }, [getApiAccessToken]);

    return { trends, scoreTrends, loading, error };
}
