import { useState, useEffect } from 'react';
import { appConfig } from '../../../config/appConfig';
import { useAuth } from '../../../auth/useAuth';
import { ConnectionStatus } from '../types';

export const useConnectionStatus = () => {
    const { getApiAccessToken } = useAuth();
    const [status, setStatus] = useState<ConnectionStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchStatus = async () => {
        setLoading(true);
        setError(null);
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/devdata/connection`, {
                headers: { 'X-MS-TOKEN-AAD': token },
            });

            if (!response.ok) throw new Error(`Server error: ${response.status}`);
            const data = await response.json();
            setStatus(data);
        } catch (err: any) {
            setError(err.message || 'Failed to fetch connection status');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStatus();
    }, []);

    return { status, loading, error, refresh: fetchStatus };
};
