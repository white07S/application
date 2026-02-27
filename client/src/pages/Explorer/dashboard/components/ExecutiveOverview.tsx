import React from 'react';
import type { ExecutiveOverviewData } from '../types';
import { CHART_SERIES } from '../chartColors';
import KPICard from './cards/KPICard';
import SummaryCard from './cards/SummaryCard';
import ScoreDistributionChart from './charts/ScoreDistributionChart';
import CriterionRadarChart from './charts/CriterionRadarChart';
import AttributeBarChart from './charts/AttributePieChart';
import FunctionBarChart from './charts/FunctionBarChart';

interface ExecutiveOverviewProps {
    data: ExecutiveOverviewData;
}

const EMPTY_SUMMARY: ExecutiveOverviewData['summary'] = { total_controls: 0, total_l1: 0, total_l2: 0, active_controls: 0, inactive_controls: 0, key_controls: 0, sox_relevant: 0, ccar_relevant: 0, bcbs239_relevant: 0 };
const EMPTY_DIST: ExecutiveOverviewData['l1_score_dist'] = { distribution: {}, avg_score: null, median_score: null, total_assessed: 0 };

const ExecutiveOverview: React.FC<ExecutiveOverviewProps> = ({ data }) => {
    const summary = data.summary ?? EMPTY_SUMMARY;
    const totalAll = data.total_all_controls ?? 0;
    const l1_score_dist = data.l1_score_dist ?? EMPTY_DIST;
    const l2_score_dist = data.l2_score_dist ?? EMPTY_DIST;
    const criterion_pass_rates = data.criterion_pass_rates ?? [];
    const attribute_distributions = data.attribute_distributions ?? [];
    const top_functions = data.top_functions ?? [];
    const top_risk_themes = data.top_risk_themes ?? [];

    const prevDetDist = attribute_distributions.find(d => d.field === 'preventative_detective');
    const manualAutoDist = attribute_distributions.find(d => d.field === 'manual_automated');
    const execFreqDist = attribute_distributions.find(d => d.field === 'execution_frequency');

    return (
        <div className="space-y-4">
            {/* KPI Row */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                <KPICard
                    label="Controls in Scope"
                    value={summary.total_controls}
                    icon="tune"
                    subtitle={`${totalAll.toLocaleString()} total in portfolio`}
                />
                <KPICard label="Level 1 (KPCs)" value={summary.total_l1} icon="looks_one" />
                <KPICard label="Level 2 (KPCis)" value={summary.total_l2} icon="looks_two" />
                <KPICard label="Active" value={summary.active_controls} icon="check_circle" color="text-green-600" />
                <KPICard label="Key Controls" value={summary.key_controls} icon="key" />
                <KPICard label="SOX Relevant" value={summary.sox_relevant} icon="policy" />
            </div>

            {/* Score Distributions */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <SummaryCard title="L1 Score Distribution (out of 7)" icon="bar_chart">
                    <div className="flex items-center gap-3 mb-2 text-[10px] text-text-sub">
                        <span>Avg: <strong className="text-text-main">{l1_score_dist.avg_score ?? 'N/A'}</strong></span>
                        <span>Median: <strong className="text-text-main">{l1_score_dist.median_score ?? 'N/A'}</strong></span>
                        <span>Assessed: <strong className="text-text-main">{l1_score_dist.total_assessed.toLocaleString()}</strong></span>
                    </div>
                    <ScoreDistributionChart distribution={l1_score_dist.distribution} maxScore={7} label="L1 Controls" color={CHART_SERIES[0]} />
                </SummaryCard>

                <SummaryCard title="L2 Score Distribution (out of 14)" icon="bar_chart">
                    <div className="flex items-center gap-3 mb-2 text-[10px] text-text-sub">
                        <span>Avg: <strong className="text-text-main">{l2_score_dist.avg_score ?? 'N/A'}</strong></span>
                        <span>Median: <strong className="text-text-main">{l2_score_dist.median_score ?? 'N/A'}</strong></span>
                        <span>Assessed: <strong className="text-text-main">{l2_score_dist.total_assessed.toLocaleString()}</strong></span>
                    </div>
                    <ScoreDistributionChart distribution={l2_score_dist.distribution} maxScore={14} label="L2 Controls" color={CHART_SERIES[1]} />
                </SummaryCard>
            </div>

            {/* Criterion Radar */}
            {criterion_pass_rates.length > 0 && (
                <SummaryCard title="Criterion Radar" icon="radar">
                    <CriterionRadarChart criteria={criterion_pass_rates} />
                </SummaryCard>
            )}

            {/* Attribute Distributions */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                {prevDetDist && (
                    <SummaryCard title="Preventative vs Detective" icon="shield">
                        <AttributeBarChart values={prevDetDist.values} />
                    </SummaryCard>
                )}
                {manualAutoDist && (
                    <SummaryCard title="Automation Level" icon="precision_manufacturing">
                        <AttributeBarChart values={manualAutoDist.values} />
                    </SummaryCard>
                )}
                {execFreqDist && (
                    <SummaryCard title="Execution Frequency" icon="schedule">
                        <AttributeBarChart values={execFreqDist.values} />
                    </SummaryCard>
                )}
            </div>

            {/* Function & Risk Theme Breakdowns */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <SummaryCard title="Controls by Function" icon="apartment">
                    <FunctionBarChart
                        items={top_functions.slice(0, 15).map(f => ({ name: f.name, value: f.control_count }))}
                        height={Math.max(200, Math.min(top_functions.length, 15) * 22)}
                    />
                </SummaryCard>

                <SummaryCard title="Controls by Risk Theme" icon="category">
                    <FunctionBarChart
                        items={top_risk_themes.slice(0, 15).map(t => ({ name: t.name, value: t.control_count }))}
                        color={CHART_SERIES[2]}
                        height={Math.max(200, Math.min(top_risk_themes.length, 15) * 22)}
                    />
                </SummaryCard>
            </div>
        </div>
    );
};

export default ExecutiveOverview;
