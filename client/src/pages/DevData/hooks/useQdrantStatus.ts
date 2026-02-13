import { useState, useEffect } from 'react';
import { appConfig } from '../../../config/appConfig';
import { useAuth } from '../../../auth/useAuth';

interface QdrantStatus {
    collection_name: string;
    points_count: number;
    vectors_count: number;
    status: string;
    named_vectors: string[];
    indexing_progress?: number;
    indexed_vectors_count?: number;
}

export function useQdrantStatus() {
    const { getApiAccessToken } = useAuth();
    const [status, setStatus] = useState<QdrantStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchStatus = async () => {
        setLoading(true);
        setError(null);
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/devdata/qdrant/stats`, {
                headers: { 'X-MS-TOKEN-AAD': token },
            });

            if (response.status === 503) {
                // Qdrant not available is not really an error
                setStatus(null);
            } else if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            } else {
                const data = await response.json();
                setStatus(data);
            }
        } catch (err: any) {
            setError(err.message || 'Failed to fetch Qdrant status');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStatus();
    }, []);

    return { status, loading, error, refresh: fetchStatus };
}