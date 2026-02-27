import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useAuth } from '../../../../../auth/useAuth';
import { fetchControlDescriptions } from '../../../api/explorerApi';
import type { ControlBrief } from '../../types';

interface Props {
    controlId: string;
    score: number;
    rank: number;
    category?: string | null;
    expanded: boolean;
    onToggle: () => void;
}

const CATEGORY_STYLES: Record<string, { label: string; className: string }> = {
    near_duplicate: { label: 'Near Duplicate', className: 'bg-red-100 text-red-700' },
    weak_similar: { label: 'Weak Similar', className: 'bg-amber-100 text-amber-700' },
};

export const LinkedControlCard: React.FC<Props> = ({ controlId, score, rank, category, expanded, onToggle }) => {
    const { getApiAccessToken } = useAuth();
    const [brief, setBrief] = useState<ControlBrief | null>(null);
    const [loading, setLoading] = useState(false);

    // Lazy-load description on first expand
    useEffect(() => {
        if (!expanded || brief) return;

        let cancelled = false;
        (async () => {
            setLoading(true);
            try {
                const token = await getApiAccessToken();
                if (!token || cancelled) return;
                const res = await fetchControlDescriptions(token, [controlId]);
                if (!cancelled && res.controls.length > 0) {
                    setBrief(res.controls[0]);
                }
            } catch {
                // silent
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [expanded, brief, controlId, getApiAccessToken]);

    return (
        <div className="border-b border-border-light/50 last:border-b-0">
            <button
                onClick={onToggle}
                className="flex items-center gap-2 w-full py-1.5 px-1 text-left hover:bg-surface-light rounded transition-colors"
            >
                <span className="text-[10px] text-text-sub w-4 text-right font-mono shrink-0">#{rank}</span>
                <span className="text-[11px] font-mono text-text-main">{controlId}</span>
                {category && CATEGORY_STYLES[category] && (
                    <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-sm ml-auto ${CATEGORY_STYLES[category].className}`}>
                        {CATEGORY_STYLES[category].label}
                    </span>
                )}
                <span className={`text-[10px] text-text-sub ${category ? 'ml-1' : 'ml-auto'} mr-1 font-mono`}>
                    {(score * 100).toFixed(1)}%
                </span>
                {expanded
                    ? <ChevronDown size={12} className="text-text-sub shrink-0" />
                    : <ChevronRight size={12} className="text-text-sub shrink-0" />
                }
            </button>
            {expanded && (
                <div className="ml-6 mb-1.5 px-2 py-1.5 rounded bg-surface-light">
                    {loading ? (
                        <div className="flex items-center gap-1 text-[10px] text-text-sub">
                            <span className="material-symbols-outlined animate-spin text-[12px]">progress_activity</span>
                            Loading...
                        </div>
                    ) : brief ? (
                        <div>
                            {brief.control_title && (
                                <div className="text-[11px] font-medium text-text-main mb-0.5">{brief.control_title}</div>
                            )}
                            {brief.control_description && (
                                <p className="text-[10px] text-text-sub leading-relaxed line-clamp-4">{brief.control_description}</p>
                            )}
                            <div className="flex gap-2 mt-1 text-[9px] text-text-sub">
                                {brief.hierarchy_level && <span>{brief.hierarchy_level}</span>}
                                {brief.control_status && <span>{brief.control_status}</span>}
                            </div>
                        </div>
                    ) : (
                        <span className="text-[10px] text-text-sub">No details available</span>
                    )}
                </div>
            )}
        </div>
    );
};
