import React from 'react';
import type { ControlDetailData } from '../types';

interface Props {
    data: ControlDetailData;
}

export const ControlDetailHeader: React.FC<Props> = ({ data }) => {
    const c = data.control;
    const status = c.control_status || 'Unknown';
    const isActive = status === 'Active';
    const level = c.hierarchy_level || '';
    const isL1 = level === 'Level 1';

    return (
        <div className="px-4 py-3 border-b border-border-light shrink-0">
            <div className="flex items-center gap-2 mb-1">
                <span className="text-[13px] font-semibold text-text-main font-mono">{c.control_id}</span>
                <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wide ${
                    isActive ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'
                }`}>
                    {status}
                </span>
                {level && (
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wide ${
                        isL1 ? 'bg-blue-50 text-blue-700' : 'bg-indigo-50 text-indigo-700'
                    }`}>
                        {isL1 ? 'L1 (KPC)' : 'L2 (KPCi)'}
                    </span>
                )}
                {c.key_control && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wide bg-amber-50 text-amber-700">
                        Key
                    </span>
                )}
            </div>
            {c.control_title && (
                <p className="text-[11px] text-text-sub leading-tight line-clamp-2 pr-8">{c.control_title}</p>
            )}
        </div>
    );
};
