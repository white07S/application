/**
 * Main hook for fetching dashboard data based on active tab and filters.
 */

import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../../../auth/useAuth';
import type { AppliedSidebarFilters } from '../../controls/types';
import type {
    DashboardTab,
    ExecutiveOverviewData,
    RegulatoryComplianceData,
} from '../types';
import {
    fetchExecutiveOverview,
    fetchRegulatoryCompliance,
} from '../api/dashboardApi';
import { buildDashboardFilters } from './useDashboardFilters';

export type DashboardData =
    | ExecutiveOverviewData
    | RegulatoryComplianceData
    | null;

export function useDashboardData(
    activeTab: DashboardTab,
    appliedFilters: AppliedSidebarFilters,
) {
    const [data, setData] = useState<DashboardData>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const { getApiAccessToken } = useAuth();
    const abortRef = useRef<AbortController | null>(null);

    useEffect(() => {
        // These tabs are handled by their own existing components
        if (activeTab === 'controls' || activeTab === 'similarity' || activeTab === 'history') {
            return;
        }

        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;

        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const token = await getApiAccessToken();
                if (!token || controller.signal.aborted) return;

                const filters = buildDashboardFilters(appliedFilters);
                let result: DashboardData = null;

                switch (activeTab) {
                    case 'overview':
                        result = await fetchExecutiveOverview(token, filters, controller.signal);
                        break;
                    case 'regulatory':
                        result = await fetchRegulatoryCompliance(token, filters, controller.signal);
                        break;
                }

                if (!controller.signal.aborted) {
                    setData(result);
                    setLoading(false);
                }
            } catch (err: any) {
                if (err?.name === 'AbortError') return;
                setError(err?.message || 'Failed to load dashboard data');
                setLoading(false);
            }
        };

        fetchData();
        return () => controller.abort();
    }, [activeTab, appliedFilters, getApiAccessToken]);

    return { data, loading, error };
}
