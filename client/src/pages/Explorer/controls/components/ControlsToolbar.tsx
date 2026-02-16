import React from 'react';
import { ControlsViewState, ControlsAction, GroupByField } from '../types';
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
    return (
        <div className="flex items-center gap-3 pb-3 border-b border-border-light">
            {/* Search */}
            <div className="flex-1 min-w-0">
                <ControlsSearchBar
                    value={state.searchQuery}
                    searchMode={state.searchMode}
                    semanticFeatures={state.semanticFeatures}
                    dispatch={dispatch}
                />
            </div>

            {/* Group By */}
            <div className="flex items-center gap-1.5 flex-shrink-0">
                <span className="text-[10px] text-text-sub uppercase font-medium tracking-wide">Group by</span>
                <select
                    value={state.groupBy}
                    onChange={(e) => dispatch({ type: 'SET_GROUP_BY', payload: e.target.value as GroupByField })}
                    className="text-xs border border-border-light rounded px-2 py-1 bg-white text-text-main focus:ring-1 focus:ring-primary focus:border-primary"
                >
                    {GROUP_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                </select>
            </div>

            {/* View toggle */}
            <div className="flex border border-border-light rounded overflow-hidden flex-shrink-0">
                <button className="p-1 bg-primary/10 text-primary" title="List view">
                    <span className="material-symbols-outlined text-[16px]">view_list</span>
                </button>
                <button className="p-1 text-text-sub/40 cursor-not-allowed" title="Grid view — Coming soon">
                    <span className="material-symbols-outlined text-[16px]">grid_view</span>
                </button>
            </div>
        </div>
    );
};
