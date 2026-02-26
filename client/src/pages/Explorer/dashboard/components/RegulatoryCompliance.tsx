import React from 'react';
import type { RegulatoryComplianceData } from '../types';
import { CHART_PRIMARY } from '../chartColors';
import SummaryCard from './cards/SummaryCard';
import RegulatoryBadge from './cards/RegulatoryBadge';
import ScoreDistributionChart from './charts/ScoreDistributionChart';
import FunctionBarChart from './charts/FunctionBarChart';

interface RegulatoryComplianceProps {
    data: RegulatoryComplianceData;
}

const EMPTY_SUMMARY: RegulatoryComplianceData['summary'] = { total_controls: 0, total_l1: 0, total_l2: 0, active_controls: 0, inactive_controls: 0, key_controls: 0, sox_relevant: 0, ccar_relevant: 0, bcbs239_relevant: 0 };
const EMPTY_DIST: RegulatoryComplianceData['sox_score_dist'] = { distribution: {}, avg_score: null, median_score: null, total_assessed: 0 };

const RegulatoryCompliance: React.FC<RegulatoryComplianceProps> = ({ data }) => {
    const summary = data.summary ?? EMPTY_SUMMARY;
    const sox_controls = data.sox_controls ?? 0;
    const ccar_controls = data.ccar_controls ?? 0;
    const bcbs239_controls = data.bcbs239_controls ?? 0;
    const sox_by_function = data.sox_by_function ?? [];
    const sox_score_dist = data.sox_score_dist ?? EMPTY_DIST;

    return (
        <div className="space-y-4">
            {/* Regulatory KPI Badges */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <RegulatoryBadge label="SOX Relevant" count={sox_controls} total={summary.total_controls} />
                <RegulatoryBadge label="CCAR Relevant" count={ccar_controls} total={summary.total_controls} />
                <RegulatoryBadge label="BCBS 239 Relevant" count={bcbs239_controls} total={summary.total_controls} />
            </div>

            {/* SOX Score Distribution + SOX by Function */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <SummaryCard title="SOX Controls - L1 Score Distribution" icon="bar_chart">
                    {sox_score_dist.total_assessed > 0 ? (
                        <>
                            <div className="flex items-center gap-3 mb-2 text-[10px] text-text-sub">
                                <span>Avg: <strong className="text-text-main">{sox_score_dist.avg_score ?? 'N/A'}</strong></span>
                                <span>Assessed: <strong className="text-text-main">{sox_score_dist.total_assessed.toLocaleString()}</strong></span>
                            </div>
                            <ScoreDistributionChart
                                distribution={sox_score_dist.distribution}
                                maxScore={7}
                                label="SOX L1 Controls"
                                color={CHART_PRIMARY}
                            />
                        </>
                    ) : (
                        <div className="flex items-center justify-center h-40 text-text-sub text-xs">
                            No SOX controls with AI scores available
                        </div>
                    )}
                </SummaryCard>

                <SummaryCard title="SOX Controls by Function" icon="apartment">
                    {sox_by_function.length > 0 ? (
                        <FunctionBarChart
                            items={sox_by_function.slice(0, 15).map(f => ({ name: f.name, value: f.control_count }))}
                            height={Math.max(200, Math.min(sox_by_function.length, 15) * 22)}
                        />
                    ) : (
                        <div className="flex items-center justify-center h-40 text-text-sub text-xs">
                            No SOX controls with function assignments
                        </div>
                    )}
                </SummaryCard>
            </div>

            {/* Summary Stats */}
            <SummaryCard title="Regulatory Coverage Summary" icon="gavel">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-2">
                    <StatBlock label="Total Controls" value={summary.total_controls} />
                    <StatBlock label="Active Controls" value={summary.active_controls} />
                    <StatBlock label="Key Controls" value={summary.key_controls} />
                    <StatBlock
                        label="Regulatory Coverage"
                        value={`${summary.total_controls > 0 ? Math.round(((sox_controls + ccar_controls + bcbs239_controls) / summary.total_controls) * 100) : 0}%`}
                    />
                </div>
            </SummaryCard>
        </div>
    );
};

const StatBlock: React.FC<{ label: string; value: string | number }> = ({ label, value }) => (
    <div className="text-center">
        <div className="text-[10px] text-text-sub uppercase tracking-wider">{label}</div>
        <div className="text-xl font-semibold text-text-main mt-0.5">
            {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
    </div>
);

export default RegulatoryCompliance;
