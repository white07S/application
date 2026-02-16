import React, { useState } from 'react';
import { AIEnrichment } from '../types';

interface Props {
    ai: AIEnrichment;
}

const L1_LABELS: Record<string, string> = {
    what: 'What',
    where: 'Where',
    who: 'Who',
    when: 'When',
    why: 'Why',
    what_why: 'What-Why',
    risk_theme: 'Risk Theme',
};

const L2_LABELS: Record<string, string> = {
    frequency: 'Frequency',
    preventative_detective: 'Prev./Det.',
    automation_level: 'Automation',
    followup: 'Follow-up',
    escalation: 'Escalation',
    evidence: 'Evidence',
    abbreviations: 'Abbreviations',
};

export const ControlCardAI: React.FC<Props> = ({ ai }) => {
    const [detailsOpen, setDetailsOpen] = useState(false);
    const entries = Object.entries(ai.criteria);
    const yesCount = entries.filter(([, v]) => v.yes_no).length;
    const labels = ai.type === 'L1' ? L1_LABELS : L2_LABELS;

    return (
        <div className="flex flex-col gap-2 p-3 min-w-0">
            {/* Score bar */}
            <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-text-main">{yesCount}/7</span>
                <div className="flex gap-0.5">
                    {entries.map(([key, val]) => (
                        <div
                            key={key}
                            className={`w-3.5 h-3.5 rounded-sm ${val.yes_no ? 'bg-green-500' : 'bg-gray-200'}`}
                            title={`${labels[key] || key}: ${val.yes_no ? 'Yes' : 'No'}`}
                        />
                    ))}
                </div>
                <span className="text-[10px] text-text-sub">{ai.type}</span>
            </div>

            {/* Expandable criteria */}
            <button
                onClick={() => setDetailsOpen(!detailsOpen)}
                className="flex items-center gap-1 text-[10px] text-text-sub hover:text-primary font-medium w-fit"
            >
                <span className={`material-symbols-outlined text-[12px] transition-transform ${detailsOpen ? 'rotate-180' : ''}`}>
                    expand_more
                </span>
                {detailsOpen ? 'Hide' : 'Show'} details
            </button>

            {detailsOpen && (
                <div className="space-y-1">
                    {entries.map(([key, val]) => (
                        <div key={key} className="flex items-start gap-1.5">
                            <span className={`material-symbols-outlined text-[12px] mt-0.5 flex-shrink-0 ${val.yes_no ? 'text-green-600' : 'text-red-400'}`}>
                                {val.yes_no ? 'check_circle' : 'cancel'}
                            </span>
                            <div className="min-w-0">
                                <span className="text-[10px] font-medium text-text-main">{labels[key] || key}</span>
                                <p className="text-[10px] text-text-sub leading-tight">{val.detail}</p>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Linked controls */}
            {ai.linked_control_ids.length > 0 && (
                <div>
                    <span className="text-[10px] text-text-sub uppercase font-medium tracking-wide block mb-0.5">
                        Linked Controls
                    </span>
                    <div className="flex flex-wrap gap-1">
                        {ai.linked_control_ids.map((id) => (
                            <span key={id} className="font-mono text-[10px] text-primary bg-primary/5 px-1.5 py-0.5 rounded-sm border border-primary/10">
                                {id}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Coming soon items */}
            <div className="space-y-1 pt-1 border-t border-border-light">
                {['Linked Issues', 'Linked Policies', 'Linked Events'].map((item) => (
                    <div key={item} className="flex items-center gap-1">
                        <span className="material-symbols-outlined text-[10px] text-text-sub">lock</span>
                        <span className="text-[10px] text-text-sub italic">{item} — Coming soon</span>
                    </div>
                ))}
            </div>
        </div>
    );
};
