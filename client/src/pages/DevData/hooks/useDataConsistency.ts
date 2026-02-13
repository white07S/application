import { useState, useEffect } from 'react';
import { appConfig } from '../../../config/appConfig';
import { useAuth } from '../../../auth/useAuth';

interface DataConsistency {
    postgres_controls: number;
    qdrant_points: number;
    is_consistent: boolean;
    difference: number;
}

export function useDataConsistency() {
    const { getApiAccessToken } = useAuth();
    const [data, setData] = useState<DataConsistency | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchConsistency = async () => {
        setLoading(true);
        setError(null);
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/devdata/consistency`, {
                headers: { 'X-MS-TOKEN-AAD': token },
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const result = await response.json();
            setData(result);
        } catch (err: any) {
            setError(err.message || 'Failed to fetch consistency data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchConsistency();
    }, []);

    return { data, loading, error, refresh: fetchConsistency };
}