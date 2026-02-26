import React, { useEffect, useRef, useState } from 'react';
import type { AppliedSidebarFilters } from '../../controls/types';
import type { LifecycleHeatmapData } from '../types';
import { CHART_SERIES } from '../chartColors';
import { useTrends } from '../hooks/useTrends';
import { buildDashboardFilters } from '../hooks/useDashboardFilters';
import { fetchLifecycleHeatmap } from '../api/dashboardApi';
import { useAuth } from '../../../../auth/useAuth';
import SummaryCard from './cards/SummaryCard';
import TrendLineChart from './charts/TrendLineChart';
import LifecycleHeatmap from './charts/LifecycleHeatmap';

interface HistoryTrackingProps {
    appliedFilters: AppliedSidebarFilters;
}

const HistoryTracking: React.FC<HistoryTrackingProps> = ({ appliedFilters }) => {
    const { trends, scoreTrends, loading, error } = useTrends();
    const { getApiAccessToken } = useAuth();

    const [lifecycle, setLifecycle] = useState<LifecycleHeatmapData | null>(null);
    const [lifecycleLoading, setLifecycleLoading] = useState(false);
    const abortRef = useRef<AbortController | null>(null);

    useEffect(() => {
        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;

        const load = async () => {
            setLifecycleLoading(true);
            try {
                const token = await getApiAccessToken();
                if (!token || controller.signal.aborted) return;
                const filters = buildDashboardFilters(appliedFilters);
                const result = await fetchLifecycleHeatmap(token, filters, controller.signal);
                if (!controller.signal.aborted) {
                    setLifecycle(result);
                    setLifecycleLoading(false);
                }
            } catch (err: any) {
                if (err?.name === 'AbortError') return;
                setLifecycleLoading(false);
            }
        };

        load();
        return () => controller.abort();
    }, [appliedFilters, getApiAccessToken]);

    return (
        <div className="space-y-4">
            {/* Lifecycle Heatmap — Created vs Retired */}
            <SummaryCard title="Controls Created vs Retired (Last 12 Months)" icon="calendar_month">
                {lifecycleLoading ? (
                    <div className="flex items-center justify-center h-24 text-text-sub">
                        <span className="material-symbols-outlined animate-spin text-[16px] mr-2">progress_activity</span>
                        <span className="text-xs">Loading lifecycle data...</span>
                    </div>
                ) : lifecycle && lifecycle.months.length > 0 ? (
                    <LifecycleHeatmap months={lifecycle.months} />
                ) : (
                    <div className="flex items-center justify-center h-24 text-text-sub text-xs">
                        No lifecycle data available
                    </div>
                )}
            </SummaryCard>

            {/* Snapshot-based trends below */}
            {loading && (
                <div className="flex items-center justify-center h-40 text-text-sub">
                    <span className="material-symbols-outlined animate-spin text-[20px] mr-2">progress_activity</span>
                    <span className="text-xs">Loading trend data...</span>
                </div>
            )}

            {error && (
                <div className="flex items-center justify-center h-40 text-text-sub">
                    <span className="material-symbols-outlined text-[20px] mr-2">error</span>
                    <span className="text-xs">{error}</span>
                </div>
            )}

            {!loading && !error && trends && trends.points.length > 0 && (
                <>
                    <div className="flex items-center gap-2 text-[10px] text-text-sub">
                        <span className="material-symbols-outlined text-[14px]">info</span>
                        {trends.total_snapshots} snapshot{trends.total_snapshots !== 1 ? 's' : ''} available
                    </div>

                    {/* Controls Over Time */}
                    <SummaryCard title="Controls Over Time" icon="show_chart">
                        <TrendLineChart
                            labels={trends.points.map(p => fmtDate(p.snapshot_at))}
                            datasets={[
                                { label: 'Total Controls', data: trends.points.map(p => p.total_controls), color: CHART_SERIES[0] },
                                { label: 'Active Controls', data: trends.points.map(p => p.active_controls), color: CHART_SERIES[1] },
                            ]}
                            yAxisLabel="Count"
                        />
                    </SummaryCard>

                    {/* Average Score Over Time */}
                    <SummaryCard title="Average AI Score Over Time" icon="trending_up">
                        <TrendLineChart
                            labels={trends.points.map(p => fmtDate(p.snapshot_at))}
                            datasets={[
                                { label: 'Avg L1 Score (out of 7)', data: trends.points.map(p => p.avg_l1_score), color: CHART_SERIES[0] },
                                { label: 'Avg L2 Score (out of 14)', data: trends.points.map(p => p.avg_l2_score), color: CHART_SERIES[2] },
                            ]}
                            yAxisLabel="Score"
                        />
                    </SummaryCard>

                    {/* Zero / Full Score Trend */}
                    <SummaryCard title="Zero & Full Score Controls" icon="contrast">
                        <TrendLineChart
                            labels={trends.points.map(p => fmtDate(p.snapshot_at))}
                            datasets={[
                                { label: 'Full Marks', data: trends.points.map(p => p.controls_scoring_full_marks), color: CHART_SERIES[0] },
                                { label: 'Zero Score', data: trends.points.map(p => p.controls_scoring_zero), color: CHART_SERIES[1] },
                            ]}
                            yAxisLabel="Controls"
                        />
                    </SummaryCard>

                    {/* Score Distribution Shift */}
                    {scoreTrends && scoreTrends.l1_trend.length > 1 && (
                        <SummaryCard title="L1 Avg Score Trend" icon="stacked_line_chart">
                            <TrendLineChart
                                labels={scoreTrends.l1_trend.map(p => fmtDate(p.snapshot_at, true))}
                                datasets={[
                                    { label: 'Avg L1 Score', data: scoreTrends.l1_trend.map(p => p.avg_score), color: CHART_SERIES[0] },
                                ]}
                                yAxisLabel="Score"
                            />
                        </SummaryCard>
                    )}
                </>
            )}

            {!loading && !error && (!trends || trends.points.length === 0) && (
                <div className="flex flex-col items-center justify-center h-40 text-text-sub">
                    <span className="material-symbols-outlined text-[28px] mb-2">timeline</span>
                    <span className="text-xs font-medium">No snapshot trend data yet</span>
                    <span className="text-[10px] mt-1">Snapshot trends will appear after multiple ingestion runs</span>
                </div>
            )}
        </div>
    );
};

const fmtDate = (iso: string, short = false): string => {
    const d = new Date(iso);
    return short
        ? d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
        : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' });
};

export default HistoryTracking;
