import React, { useState } from 'react';
import type { ControlDetailData } from '../../types';
import { CriterionRow } from '../components/CriterionRow';
import { LinkedControlCard } from '../components/LinkedControlCard';

interface Props {
    data: ControlDetailData;
}

const L1_CRITERIA = [
    { key: 'what', label: 'What' },
    { key: 'where', label: 'Where' },
    { key: 'who', label: 'Who' },
    { key: 'when', label: 'When' },
    { key: 'why', label: 'Why' },
    { key: 'what_why', label: 'What & Why' },
    { key: 'risk_theme', label: 'Risk Theme' },
];

const L2_CRITERIA = [
    { key: 'frequency', label: 'Frequency' },
    { key: 'preventative_detective', label: 'Prev / Detective' },
    { key: 'automation_level', label: 'Automation Level' },
    { key: 'followup', label: 'Follow-up' },
    { key: 'escalation', label: 'Escalation' },
    { key: 'evidence', label: 'Evidence' },
    { key: 'abbreviations', label: 'Abbreviations' },
];

const COMING_SOON = [
    { label: 'Linked Events', icon: 'event' },
    { label: 'Linked Issues', icon: 'bug_report' },
    { label: 'Linked Policies', icon: 'gavel' },
];

export const AITab: React.FC<Props> = ({ data }) => {
    const ai = data.ai;
    const level = data.control.hierarchy_level;
    const isL2 = level === 'Level 2';
    const parentScore = data.parent_l1_score;
    const similarControls = data.similar_controls;

    // Expanded linked controls state
    const [expandedLinked, setExpandedLinked] = useState<Set<string>>(new Set());

    if (!ai) {
        return (
            <div className="flex flex-col items-center justify-center h-32 text-text-sub">
                <span className="material-symbols-outlined text-[24px] mb-1">auto_awesome</span>
                <span className="text-xs">No AI enrichment data available</span>
            </div>
        );
    }

    // Compute scores
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const aiRecord = ai as any;
    const getYesNo = (key: string): boolean => {
        const val = aiRecord[`${key}_yes_no`];
        return typeof val === 'string' && val.toLowerCase() === 'yes';
    };
    const getDetails = (key: string): string | null => {
        const val = aiRecord[`${key}_details`];
        return typeof val === 'string' && val ? val : null;
    };

    const ownCriteria = isL2 ? L2_CRITERIA : L1_CRITERIA;
    const ownYesCount = ownCriteria.filter(c => getYesNo(c.key)).length;

    // For L2: total = own 7 + parent 7
    const parentYes = parentScore?.yes_count ?? 0;
    const totalScore = isL2 ? ownYesCount + parentYes : ownYesCount;
    const totalMax = isL2 ? 14 : 7;

    const toggleLinked = (controlId: string) => {
        setExpandedLinked(prev => {
            const next = new Set(prev);
            if (next.has(controlId)) next.delete(controlId);
            else next.add(controlId);
            return next;
        });
    };

    return (
        <div>
            {/* Score summary */}
            <div className="flex items-center gap-3 mb-4 p-3 bg-surface-light rounded">
                <div className="text-center">
                    <span className="text-[20px] font-bold text-text-main font-mono">{totalScore}</span>
                    <span className="text-[12px] text-text-sub">/{totalMax}</span>
                </div>
                <div className="text-[11px] text-text-sub">
                    {isL2 ? (
                        <div>
                            <div>Own criteria: {ownYesCount}/7</div>
                            <div>Inherited from parent ({parentScore?.control_id ?? '—'}): {parentYes}/7</div>
                        </div>
                    ) : (
                        <div>L1 W-Criteria Score</div>
                    )}
                </div>
            </div>

            {/* Parent criteria (for L2) */}
            {isL2 && parentScore && (
                <div className="mb-4">
                    <div className="flex items-center gap-1.5 mb-2 pb-1 border-b border-border-light">
                        <span className="material-symbols-outlined text-[14px] text-text-sub">arrow_upward</span>
                        <span className="text-[11px] font-semibold text-text-main uppercase tracking-wide">
                            Parent L1 Criteria ({parentScore.control_id})
                        </span>
                        <span className="text-[10px] text-text-sub ml-auto">{parentScore.yes_count}/{parentScore.total}</span>
                    </div>
                    {parentScore.criteria.map(c => (
                        <div key={c.key} className="flex items-center gap-2 py-0.5 px-1">
                            <span className={`inline-flex items-center justify-center w-4 h-4 rounded text-[9px] font-bold ${
                                c.yes_no ? 'bg-green-100 text-green-700' : 'bg-red-50 text-red-400'
                            }`}>
                                {c.yes_no ? 'Y' : 'N'}
                            </span>
                            <span className="text-[11px] text-text-main capitalize">{c.key.replace(/_/g, ' ')}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* Own criteria */}
            <div className="mb-4">
                <div className="flex items-center gap-1.5 mb-2 pb-1 border-b border-border-light">
                    <span className="material-symbols-outlined text-[14px] text-text-sub">checklist</span>
                    <span className="text-[11px] font-semibold text-text-main uppercase tracking-wide">
                        {isL2 ? 'L2 Operational Criteria' : 'L1 W-Criteria'}
                    </span>
                    <span className="text-[10px] text-text-sub ml-auto">{ownYesCount}/7</span>
                </div>
                {ownCriteria.map(c => (
                    <CriterionRow
                        key={c.key}
                        label={c.label}
                        yesNo={getYesNo(c.key)}
                        details={getDetails(c.key)}
                    />
                ))}
            </div>

            {/* Similar / Linked Controls */}
            {similarControls.length > 0 && (
                <div className="mb-4">
                    <div className="flex items-center gap-1.5 mb-2 pb-1 border-b border-border-light">
                        <span className="material-symbols-outlined text-[14px] text-text-sub">link</span>
                        <span className="text-[11px] font-semibold text-text-main uppercase tracking-wide">
                            Similar Controls
                        </span>
                        <span className="text-[10px] text-text-sub ml-auto">{similarControls.length}</span>
                    </div>

                    {/* Current control reference for comparison */}
                    <div className="mb-2 px-2 py-1.5 rounded border border-dashed border-border-light bg-surface-light/50">
                        <div className="flex items-center gap-1 mb-0.5">
                            <span className="material-symbols-outlined text-[12px] text-text-sub">article</span>
                            <span className="text-[10px] font-semibold text-text-sub uppercase tracking-wide">This Control</span>
                            <span className="text-[10px] font-mono text-text-sub ml-auto">{data.control.control_id}</span>
                        </div>
                        {data.control.control_title && (
                            <p className="text-[10px] font-medium text-text-main mb-0.5">{data.control.control_title}</p>
                        )}
                        {data.control.control_description && (
                            <p className="text-[10px] text-text-sub leading-relaxed line-clamp-3">{data.control.control_description}</p>
                        )}
                    </div>

                    {similarControls.map(sc => (
                        <LinkedControlCard
                            key={sc.control_id}
                            controlId={sc.control_id}
                            score={sc.score}
                            rank={sc.rank}
                            expanded={expandedLinked.has(sc.control_id)}
                            onToggle={() => toggleLinked(sc.control_id)}
                        />
                    ))}
                </div>
            )}

            {/* Coming Soon */}
            <div className="mb-4">
                <div className="flex items-center gap-1.5 mb-2 pb-1 border-b border-border-light">
                    <span className="material-symbols-outlined text-[14px] text-text-sub">upcoming</span>
                    <span className="text-[11px] font-semibold text-text-main uppercase tracking-wide">Coming Soon</span>
                </div>
                {COMING_SOON.map(item => (
                    <div key={item.label} className="flex items-center gap-2 py-1.5 px-2 text-text-sub">
                        <span className="material-symbols-outlined text-[14px]">{item.icon}</span>
                        <span className="text-[11px]">{item.label}</span>
                        <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-400 font-medium">
                            Coming Soon
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
};
