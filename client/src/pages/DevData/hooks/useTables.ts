import { useState, useEffect } from 'react';
import { appConfig } from '../../../config/appConfig';
import { useAuth } from '../../../auth/useAuth';
import { TableInfo } from '../types';

export const useTables = () => {
    const { getApiAccessToken } = useAuth();
    const [tables, setTables] = useState<TableInfo[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchTables = async () => {
        setLoading(true);
        setError(null);
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/devdata/tables`, {
                headers: { 'X-MS-TOKEN-AAD': token },
            });

            if (!response.ok) throw new Error(`Server error: ${response.status}`);
            const data = await response.json();
            setTables(data.tables);
        } catch (err: any) {
            setError(err.message || 'Failed to fetch tables');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTables();
    }, []);

    return { tables, loading, error, refresh: fetchTables };
};
