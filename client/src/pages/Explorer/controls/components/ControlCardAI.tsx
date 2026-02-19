import React from 'react';
import { Sparkles } from 'lucide-react';
import { AIEnrichment, ParentL1Score, SimilarControl } from '../types';

interface Props {
    ai: AIEnrichment;
    parentScore?: ParentL1Score | null;
    similarControls?: SimilarControl[];
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

export const ControlCardAI: React.FC<Props> = ({ ai, parentScore, similarControls = [] }) => {
    const ownEntries = Object.entries(ai.criteria);
    const ownYesCount = ownEntries.filter(([, v]) => v.yes_no).length;

    // For L2: combined score = parent L1 (7) + own L2 (7) = X/14
    // For L1: just own score = X/7
    const isL2 = ai.type === 'L2';
    const hasParent = isL2 && !!parentScore;
    const totalYes = hasParent ? parentScore.yesCount + ownYesCount : ownYesCount;
    const totalCount = hasParent ? parentScore.total + ownEntries.length : ownEntries.length;

    return (
        <div className="relative overflow-hidden flex flex-col gap-2 p-3 min-w-0">
            <div
                aria-hidden="true"
                className="pointer-events-none select-none absolute -top-1 -right-1 opacity-70"
            >
                <Sparkles className="w-12 h-12 text-primary/20" strokeWidth={1.75} />
            </div>
            <div
                aria-hidden="true"
                className="pointer-events-none select-none absolute top-8 right-7 opacity-60"
            >
                <Sparkles className="w-5 h-5 text-primary/15" strokeWidth={1.75} />
            </div>

            {/* Score display */}
            {hasParent ? (
                /* L2 with parent on page: side-by-side showing inherited + own */
                <div className="rounded-sm border border-border-light bg-white/80 px-2 py-1.5">
                    <div className="flex items-center justify-between gap-2 pr-10">
                        <div className="flex items-center gap-1 min-w-0">
                            <span className="material-symbols-outlined text-[12px] text-text-sub">family_link</span>
                            <span className="text-[10px] text-text-sub uppercase font-medium tracking-wide whitespace-nowrap">
                                Child Inheriting 7W From
                            </span>
                            <span
                                className="font-mono text-[9px] text-text-main bg-surface-light px-1 py-0.5 rounded-sm truncate max-w-[78px]"
                                title={parentScore!.controlId}
                            >
                                {parentScore!.controlId}
                            </span>
                        </div>
                        <span className="text-xs font-semibold text-text-main whitespace-nowrap mr-0.5">
                            {totalYes}/{totalCount}
                        </span>
                    </div>
                    <div className="mt-1 flex items-center gap-0.5">
                        {/* Parent's L1 blocks (inherited) */}
                        {parentScore!.criteria.map((criterion) => (
                            <div
                                key={`parent-${criterion.key}`}
                                className={`w-2 h-2 rounded-sm ${criterion.yes_no ? 'bg-emerald-500' : 'bg-gray-200'}`}
                                title={`${L1_LABELS[criterion.key] || criterion.key}: ${criterion.yes_no ? 'Yes' : 'No'} (inherited)`}
                            />
                        ))}
                        <span className="mx-1 w-px h-2.5 bg-border-light" />
                        {/* Own L2 blocks */}
                        {ownEntries.map(([key, val]) => (
                            <div
                                key={`child-${key}`}
                                className={`w-2 h-2 rounded-sm ${val.yes_no ? 'bg-green-500' : 'bg-gray-200'}`}
                                title={`${L2_LABELS[key] || key}: ${val.yes_no ? 'Yes' : 'No'}`}
                            />
                        ))}
                    </div>
                </div>
            ) : (
                /* L1: own score X/7, or L2 without parent on page: own score X/7 */
                <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-text-main">{ownYesCount}/{ownEntries.length}</span>
                    <div className="flex items-center gap-0.5">
                        {ownEntries.map(([key, val]) => (
                            <div
                                key={key}
                                className={`w-3.5 h-3.5 rounded-sm ${val.yes_no ? 'bg-green-500' : 'bg-gray-200'}`}
                                title={`${(isL2 ? L2_LABELS : L1_LABELS)[key] || key}: ${val.yes_no ? 'Yes' : 'No'}`}
                            />
                        ))}
                    </div>
                    <span className="text-[10px] text-text-sub">{ai.type}</span>
                </div>
            )}

            {/* Linked controls */}
            {similarControls.length > 0 && (
                <div>
                    <span className="text-[10px] text-text-sub uppercase font-medium tracking-wide block mb-0.5">
                        Linked Controls
                    </span>
                    <div className="flex flex-wrap gap-1">
                        {similarControls.map((sc) => {
                            const maxScore = similarControls[0]?.score || 1;
                            const intensity = Math.max(0.4, sc.score / maxScore);
                            return (
                                <span
                                    key={sc.control_id}
                                    className="inline-flex items-center gap-1 font-mono text-[10px] px-1.5 py-0.5 rounded-sm border border-primary/10"
                                    style={{ opacity: intensity, backgroundColor: `rgba(var(--color-primary-rgb, 59, 130, 246), ${0.05 + intensity * 0.1})` }}
                                    title={`Score: ${sc.score.toFixed(2)} (Rank #${sc.rank})`}
                                >
                                    <span className="text-primary">{sc.control_id}</span>
                                    <span className="text-text-sub text-[9px]">{sc.score.toFixed(2)}</span>
                                </span>
                            );
                        })}
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
