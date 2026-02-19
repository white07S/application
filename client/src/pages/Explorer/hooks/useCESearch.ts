import { useState, useEffect } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { FlatItem } from '../types';
import { fetchCEs } from '../api/explorerApi';

export function useCESearch() {
    const { getApiAccessToken } = useAuth();
    const [items, setItems] = useState<FlatItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [search, setSearch] = useState('');
    const [total, setTotal] = useState(0);
    const [hasMore, setHasMore] = useState(false);

    useEffect(() => {
        let cancelled = false;
        const timer = setTimeout(async () => {
            setLoading(true);
            setError(null);
            try {
                const token = await getApiAccessToken();
                if (!token || cancelled) return;
                const data = await fetchCEs(token, search || undefined, 1);
                if (!cancelled) {
                    setItems(data.items.map((i) => ({ id: i.id, label: i.label, description: i.description })));
                    setTotal(data.total);
                    setHasMore(data.has_more);
                }
            } catch (err: any) {
                if (!cancelled) setError(err.message || 'Failed to load entities');
            } finally {
                if (!cancelled) setLoading(false);
            }
        }, search ? 300 : 0); // Debounce when searching, immediate on initial load

        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, [search, getApiAccessToken]);

    return { items, loading, error, search, setSearch, total, hasMore };
}
