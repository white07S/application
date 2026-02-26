import React from 'react';
import type { CriterionPassRate } from '../../types';
import { HEATMAP_HIGH, HEATMAP_MID, HEATMAP_LOW } from '../../chartColors';

interface ScoreHeatmapProps {
    criteria: CriterionPassRate[];
}

const getColor = (rate: number): string => {
    if (rate >= 0.85) return HEATMAP_HIGH;
    if (rate >= 0.6) return HEATMAP_MID;
    return HEATMAP_LOW;
};

const ScoreHeatmap: React.FC<ScoreHeatmapProps> = ({ criteria }) => (
    <div className="grid grid-cols-7 gap-1">
        {criteria.map((c) => (
            <div
                key={c.criterion}
                className={`rounded px-1.5 py-1 text-center ${getColor(c.pass_rate)}`}
                title={`${c.label}: ${Math.round(c.pass_rate * 100)}% (${c.pass_count}/${c.total_count})`}
            >
                <div className="text-[9px] font-medium truncate">{c.label}</div>
                <div className="text-sm font-semibold">{Math.round(c.pass_rate * 100)}%</div>
            </div>
        ))}
    </div>
);

export default ScoreHeatmap;
