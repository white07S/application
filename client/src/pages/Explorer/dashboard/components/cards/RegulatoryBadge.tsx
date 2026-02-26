import React from 'react';

interface RegulatoryBadgeProps {
    label: string;
    count: number;
    total: number;
}

const RegulatoryBadge: React.FC<RegulatoryBadgeProps> = ({ label, count, total }) => {
    const pct = total > 0 ? Math.round((count / total) * 100) : 0;
    return (
        <div className="bg-white border border-border-light rounded-lg p-3">
            <div className="text-[10px] font-medium text-text-sub uppercase tracking-wider">{label}</div>
            <div className="text-lg font-semibold text-text-main mt-1">{count.toLocaleString()}</div>
            <div className="mt-1.5 w-full bg-gray-100 rounded-full h-1.5">
                <div
                    className="bg-lagoon h-1.5 rounded-full transition-all"
                    style={{ width: `${pct}%` }}
                />
            </div>
            <div className="text-[9px] text-text-sub mt-1">{pct}% of {total.toLocaleString()} controls</div>
        </div>
    );
};

export default RegulatoryBadge;
