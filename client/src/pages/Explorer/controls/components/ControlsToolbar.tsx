import React from 'react';
import { ControlsViewState, ControlsAction, GroupByField, DateField } from '../types';
import { ControlsSearchBar } from './ControlsSearchBar';

interface Props {
    state: ControlsViewState;
    dispatch: React.Dispatch<ControlsAction>;
}

const GROUP_OPTIONS: { value: GroupByField; label: string }[] = [
    { value: 'none', label: 'No grouping' },
    { value: 'preventative_detective', label: 'Preventative / Detective' },
    { value: 'manual_automated', label: 'Manual / Automated' },
];

export const ControlsToolbar: React.FC<Props> = ({ state, dispatch }) => {
    const AI_SCORE_OPTIONS = Array.from({ length: 14 }, (_, i) => i + 1);

    return (
        <div className="flex flex-wrap lg:flex-nowrap items-center gap-2 pb-3 border-b border-border-light">
            {/* Range (UI only) */}
            <div className="flex items-center gap-1.5 flex-shrink-0 h-8 px-2 border border-border-light rounded-sm bg-surface-light/40">
                <span className="material-symbols-outlined text-[13px] text-text-sub">date_range</span>
                <span className="text-[10px] text-text-sub uppercase font-medium tracking-wide">Range</span>
            </div>
            <input
                type="date"
                aria-label="Start date"
                value={state.dateFrom}
                onChange={(e) => dispatch({ type: 'SET_DATE_FROM', payload: e.target.value })}
                className="h-8 w-[136px] text-xs border border-border-light rounded-sm px-2 bg-white text-text-main focus:ring-1 focus:ring-primary focus:border-primary"
            />
            <input
                type="date"
                aria-label="End date"
                value={state.dateTo}
                onChange={(e) => dispatch({ type: 'SET_DATE_TO', payload: e.target.value })}
                className="h-8 w-[136px] text-xs border border-border-light rounded-sm px-2 bg-white text-text-main focus:ring-1 focus:ring-primary focus:border-primary"
            />
            <select
                aria-label="Apply range on"
                value={state.dateField}
                onChange={(e) => dispatch({ type: 'SET_DATE_FIELD', payload: e.target.value as DateField })}
                className="h-8 w-[208px] text-xs border border-border-light rounded-sm px-2 bg-white text-text-main focus:ring-1 focus:ring-primary focus:border-primary flex-shrink-0"
            >
                <option value="created_on">Control Created On</option>
                <option value="last_modified_on">Control Last Modified Date</option>
            </select>

            {/* Search */}
            <div className="flex-1 min-w-[260px]">
                <ControlsSearchBar
                    value={state.searchQuery}
                    searchMode={state.searchMode}
                    searchTags={state.searchTags}
                    semanticFeatures={state.semanticFeatures}
                    dispatch={dispatch}
                />
            </div>

            {/* AI score threshold */}
            <div className="flex items-center gap-1 flex-shrink-0">
                <span className="text-[10px] text-text-sub uppercase font-medium tracking-wide whitespace-nowrap">AI ≤</span>
                <select
                    aria-label="AI score max"
                    value={state.aiScoreMax}
                    onChange={(e) => dispatch({ type: 'SET_AI_SCORE_MAX', payload: Number(e.target.value) })}
                    className="h-8 w-[70px] text-xs border border-border-light rounded-sm px-1.5 bg-white text-text-main focus:ring-1 focus:ring-primary focus:border-primary"
                    title="Show controls with AI score less than or equal to selected value"
                >
                    {AI_SCORE_OPTIONS.map((score) => (
                        <option key={score} value={score}>{score}</option>
                    ))}
                </select>
            </div>

            {/* Group By */}
            <div className="flex items-center gap-1 flex-shrink-0 border-l border-border-light pl-1.5 ml-0.5">
                <span className="text-[10px] text-text-sub font-medium whitespace-nowrap">Group</span>
                <select
                    value={state.groupBy}
                    onChange={(e) => dispatch({ type: 'SET_GROUP_BY', payload: e.target.value as GroupByField })}
                    className="h-8 text-xs border border-border-light rounded-sm px-2 bg-white text-text-main focus:ring-1 focus:ring-primary focus:border-primary min-w-[146px]"
                >
                    {GROUP_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                </select>
            </div>
        </div>
    );
};
