import { useState, useEffect } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { fetchSourceDates, SourceDatesResponse } from '../api/explorerApi';

export interface SourceDates {
    function: string | null;
    location: string | null;
    consolidated: string | null;
}

export function useSourceDates() {
    const { getApiAccessToken } = useAuth();
    const [dates, setDates] = useState<SourceDates>({
        function: null,
        location: null,
        consolidated: null,
    });

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const token = await getApiAccessToken();
                if (!token || cancelled) return;
                const data: SourceDatesResponse = await fetchSourceDates(token);
                if (!cancelled) {
                    setDates({
                        function: data.function,
                        location: data.location,
                        consolidated: data.consolidated,
                    });
                }
            } catch {
                // Non-fatal — source dates are informational
            }
        };
        load();
        return () => { cancelled = true; };
    }, [getApiAccessToken]);

    return dates;
}
