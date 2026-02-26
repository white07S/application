import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface Props {
    label: string;
    yesNo: boolean;
    details: string | null;
}

export const CriterionRow: React.FC<Props> = ({ label, yesNo, details }) => {
    const [expanded, setExpanded] = useState(false);
    const hasDetails = !!details;

    return (
        <div className="border-b border-border-light/50 last:border-b-0">
            <button
                onClick={() => hasDetails && setExpanded(!expanded)}
                className={`flex items-center gap-2 w-full py-1 px-1 text-left ${hasDetails ? 'cursor-pointer hover:bg-surface-light' : 'cursor-default'} rounded transition-colors`}
            >
                <span className={`inline-flex items-center justify-center w-4 h-4 rounded text-[9px] font-bold shrink-0 ${
                    yesNo ? 'bg-green-100 text-green-700' : 'bg-red-50 text-red-400'
                }`}>
                    {yesNo ? 'Y' : 'N'}
                </span>
                <span className="text-[11px] text-text-main flex-1">{label}</span>
                {hasDetails && (
                    expanded
                        ? <ChevronDown size={12} className="text-text-sub shrink-0" />
                        : <ChevronRight size={12} className="text-text-sub shrink-0" />
                )}
            </button>
            {expanded && details && (
                <div className="ml-6 mb-1 px-2 py-1.5 rounded bg-surface-light text-[10px] text-text-sub leading-relaxed whitespace-pre-wrap">
                    {details}
                </div>
            )}
        </div>
    );
};
