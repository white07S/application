import React from 'react';
import type { DocQualityData } from '../types';
import { CHART_SERIES } from '../chartColors';
import SummaryCard from './cards/SummaryCard';
import ScoreDistributionChart from './charts/ScoreDistributionChart';
import CriterionRadarChart from './charts/CriterionRadarChart';
import FunctionBarChart from './charts/FunctionBarChart';

interface DocQualityMonitorProps {
    data: DocQualityData;
}

const DocQualityMonitor: React.FC<DocQualityMonitorProps> = ({ data }) => {
    const l1_score_dist = data.l1_score_dist ?? { distribution: {}, avg_score: null, median_score: null, total_assessed: 0 };
    const l2_score_dist = data.l2_score_dist ?? { distribution: {}, avg_score: null, median_score: null, total_assessed: 0 };
    const criterion_pass_rates = data.criterion_pass_rates ?? [];
    const worst_criteria = data.worst_criteria ?? [];
    const score_by_function = data.score_by_function ?? [];

    return (
        <div className="space-y-4">
            {/* Score Gauges */}
            <div className="grid grid-cols-2 gap-3">
                <div className="bg-white border border-border-light rounded-lg p-4 text-center">
                    <div className="text-[10px] text-text-sub uppercase tracking-wider mb-1">L1 Average Score</div>
                    <div className="text-3xl font-bold text-lagoon">
                        {l1_score_dist.avg_score !== null ? `${l1_score_dist.avg_score}` : 'N/A'}
                        <span className="text-sm font-normal text-text-sub"> / 7</span>
                    </div>
                    <div className="text-[10px] text-text-sub mt-1">
                        {l1_score_dist.total_assessed.toLocaleString()} controls assessed
                    </div>
                </div>
                <div className="bg-white border border-border-light rounded-lg p-4 text-center">
                    <div className="text-[10px] text-text-sub uppercase tracking-wider mb-1">L2 Average Score</div>
                    <div className="text-3xl font-bold text-slate-600">
                        {l2_score_dist.avg_score !== null ? `${l2_score_dist.avg_score}` : 'N/A'}
                        <span className="text-sm font-normal text-text-sub"> / 14</span>
                    </div>
                    <div className="text-[10px] text-text-sub mt-1">
                        {l2_score_dist.total_assessed.toLocaleString()} controls assessed
                    </div>
                </div>
            </div>

            {/* Score Distributions */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <SummaryCard title="L1 Score Histogram" icon="bar_chart">
                    <ScoreDistributionChart distribution={l1_score_dist.distribution} maxScore={7} label="L1" color={CHART_SERIES[0]} />
                </SummaryCard>
                <SummaryCard title="L2 Score Histogram" icon="bar_chart">
                    <ScoreDistributionChart distribution={l2_score_dist.distribution} maxScore={14} label="L2" color={CHART_SERIES[1]} />
                </SummaryCard>
            </div>

            {/* Worst Criteria + Radar */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <SummaryCard title="Criteria Requiring Attention" icon="warning">
                    <div className="space-y-1">
                        {worst_criteria.slice(0, 7).map(c => (
                            <div key={c.criterion} className="flex items-center justify-between py-1 border-b border-border-light last:border-0">
                                <span className="text-[11px] text-text-main">{c.label}</span>
                                <div className="flex items-center gap-2">
                                    <div className="w-20 bg-gray-100 rounded-full h-1.5">
                                        <div
                                            className={`h-1.5 rounded-full ${c.pass_rate >= 0.85 ? 'bg-emerald-500' : c.pass_rate >= 0.6 ? 'bg-amber-500' : 'bg-slate-400'}`}
                                            style={{ width: `${Math.round(c.pass_rate * 100)}%` }}
                                        />
                                    </div>
                                    <span className="text-[10px] font-medium text-text-sub w-8 text-right">
                                        {Math.round(c.pass_rate * 100)}%
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </SummaryCard>

                <SummaryCard title="Criterion Radar" icon="radar">
                    <CriterionRadarChart criteria={criterion_pass_rates} />
                </SummaryCard>
            </div>

            {/* Score by Function */}
            <SummaryCard title="Controls by Function" icon="apartment">
                <FunctionBarChart
                    items={score_by_function.map(f => ({ name: f.name, value: f.control_count }))}
                    height={Math.max(200, score_by_function.length * 20)}
                />
            </SummaryCard>
        </div>
    );
};

export default DocQualityMonitor;
