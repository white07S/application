/**
 * Dashboard API module.
 * Follows the pattern from Explorer/api/explorerApi.ts.
 */

import { appConfig } from '../../../../config/appConfig';
import type {
    ConcentrationData,
    DashboardFiltersPayload,
    ExecutiveOverviewData,
    LifecycleHeatmapData,
    RedundancyData,
    RegulatoryComplianceData,
    ScoreTrendData,
    TrendData,
} from '../types';

const BASE = `${appConfig.api.baseUrl}/api/v2/explorer/dashboard`;

async function dashboardFetch<T>(
    path: string,
    token: string,
    options?: {
        body?: object;
        signal?: AbortSignal;
        params?: Record<string, string | undefined>;
    },
): Promise<T> {
    const url = new URL(`${BASE}${path}`);
    if (options?.params) {
        Object.entries(options.params).forEach(([k, v]) => {
            if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
        });
    }

    const hasBody = options?.body !== undefined;
    const res = await fetch(url.toString(), {
        method: hasBody ? 'POST' : 'GET',
        headers: {
            'X-MS-TOKEN-AAD': token,
            ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
        },
        body: hasBody ? JSON.stringify(options!.body) : undefined,
        signal: options?.signal,
    });

    if (!res.ok) throw new Error(`Dashboard API error: ${res.status}`);
    return res.json();
}

// ── Tab endpoints (POST with filters) ────────────────────────────────────

export const fetchExecutiveOverview = (
    token: string,
    filters?: DashboardFiltersPayload,
    signal?: AbortSignal,
) => dashboardFetch<ExecutiveOverviewData>('/executive-overview', token, {
    body: filters || {},
    signal,
});

export const fetchRegulatoryCompliance = (
    token: string,
    filters?: DashboardFiltersPayload,
    signal?: AbortSignal,
) => dashboardFetch<RegulatoryComplianceData>('/regulatory-compliance', token, {
    body: filters || {},
    signal,
});

export const fetchLifecycleHeatmap = (
    token: string,
    filters?: DashboardFiltersPayload,
    signal?: AbortSignal,
) => dashboardFetch<LifecycleHeatmapData>('/lifecycle-heatmap', token, {
    body: filters || {},
    signal,
});

export const fetchConcentration = (
    token: string,
    dimension: 'roles' | 'process' | 'product' | 'service',
    filters?: DashboardFiltersPayload,
    signal?: AbortSignal,
) => dashboardFetch<ConcentrationData>(`/concentration/${dimension}`, token, {
    body: filters || {},
    signal,
});

export const fetchSimilarityRedundancy = (
    token: string,
    filters?: DashboardFiltersPayload,
    signal?: AbortSignal,
) => dashboardFetch<RedundancyData>('/similarity-redundancy', token, {
    body: filters || {},
    signal,
});

// ── Trend endpoints (GET) ────────────────────────────────────────────────

export const fetchTrends = (token: string, signal?: AbortSignal) =>
    dashboardFetch<TrendData>('/trends', token, { signal });

export const fetchScoreTrends = (token: string, signal?: AbortSignal) =>
    dashboardFetch<ScoreTrendData>('/trends/scores', token, { signal });
