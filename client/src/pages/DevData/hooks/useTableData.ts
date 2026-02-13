import { useState, useEffect, useCallback } from 'react';
import { appConfig } from '../../../config/appConfig';
import { useAuth } from '../../../auth/useAuth';
import { PaginatedRecords, RelationshipExpansion } from '../types';

export const useTableData = (tableName: string | undefined) => {
    const { getApiAccessToken } = useAuth();
    const [data, setData] = useState<PaginatedRecords | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(50);

    const fetchData = useCallback(async () => {
        if (!tableName) return;
        setLoading(true);
        setError(null);
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const response = await fetch(
                `${appConfig.api.baseUrl}/api/v2/devdata/tables/${tableName}?page=${page}&page_size=${pageSize}`,
                { headers: { 'X-MS-TOKEN-AAD': token } },
            );

            if (!response.ok) throw new Error(`Server error: ${response.status}`);
            const result = await response.json();
            setData(result);
        } catch (err: any) {
            setError(err.message || 'Failed to fetch table data');
        } finally {
            setLoading(false);
        }
    }, [tableName, page, pageSize]);

    useEffect(() => {
        setPage(1);
    }, [tableName]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const expandRelationship = async (recordId: string): Promise<RelationshipExpansion | null> => {
        try {
            const token = await getApiAccessToken();
            if (!token || !tableName) return null;

            const response = await fetch(
                `${appConfig.api.baseUrl}/api/v2/devdata/relationships/${tableName}/${encodeURIComponent(recordId)}`,
                { headers: { 'X-MS-TOKEN-AAD': token } },
            );

            if (!response.ok) throw new Error(`Server error: ${response.status}`);
            return await response.json();
        } catch (err: any) {
            console.error('Failed to expand relationship:', err);
            return null;
        }
    };

    return {
        data,
        loading,
        error,
        page,
        pageSize,
        setPage,
        setPageSize,
        refresh: fetchData,
        expandRelationship,
    };
};
