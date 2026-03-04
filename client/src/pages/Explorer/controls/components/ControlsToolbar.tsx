import React, { useState, useRef, useEffect } from 'react';
import { ControlsViewState, ControlsAction, GroupByField, DateField, L1_WS_CRITERIA, L2_WS_CRITERIA } from '../types';
import { ControlsSearchBar } from './ControlsSearchBar';

interface Props {
    state: ControlsViewState;
    dispatch: React.Dispatch<ControlsAction>;
    searchDisabled?: boolean;
}

const GROUP_OPTIONS: { value: GroupByField; label: string }[] = [
    { value: 'none', label: 'No grouping' },
    { value: 'preventative_detective', label: 'Preventative / Detective' },
    { value: 'manual_automated', label: 'Manual / Automated' },
];

export const ControlsToolbar: React.FC<Props> = ({ state, dispatch, searchDisabled }) => {
    const [wsOpen, setWsOpen] = useState(false);
    const wsRef = useRef<HTMLDivElement>(null);

    // Close dropdown on outside click
    useEffect(() => {
        if (!wsOpen) return;
        const handler = (e: MouseEvent) => {
            if (wsRef.current && !wsRef.current.contains(e.target as Node)) setWsOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [wsOpen]);

    // Build visible WS criteria based on L1/L2 toggle state
    const showL1 = state.filterLevel1;
    const showL2 = state.filterLevel2;
    const visibleCriteria: { group: string; items: readonly { key: string; label: string }[] }[] = [];
    if (showL1 || showL2) {
        visibleCriteria.push({ group: 'L1', items: L1_WS_CRITERIA });
    }
    if (showL2) {
        visibleCriteria.push({ group: 'L2', items: L2_WS_CRITERIA });
    }

    const wsCount = state.wsFilter.size;

    return (
        <div className="flex flex-col gap-2 pb-3 border-b border-border-light">
            {/* Row 1: Live filters — changes apply immediately */}
            <div className="flex flex-wrap lg:flex-nowrap items-center gap-2">
                {/* Range */}
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

                {/* Spacer */}
                <div className="flex-1" />

                {/* WS Filter dropdown */}
                <div ref={wsRef} className="relative flex-shrink-0">
                    <button
                        type="button"
                        onClick={() => setWsOpen((v) => !v)}
                        className={`h-8 px-2.5 text-[10px] uppercase font-semibold tracking-wide rounded-sm border transition-colors flex items-center gap-1 ${
                            wsCount > 0
                                ? 'bg-primary text-white border-primary'
                                : 'bg-white text-text-sub border-border-light hover:border-primary/40'
                        }`}
                        title="Filter by WS criteria where value is No"
                    >
                        <span className="material-symbols-outlined text-[14px]">checklist</span>
                        WS
                        {wsCount > 0 && (
                            <span className="bg-white/25 text-[9px] font-bold px-1 py-px rounded-sm ml-0.5">
                                {wsCount}
                            </span>
                        )}
                        <span className={`material-symbols-outlined text-[12px] transition-transform ${wsOpen ? 'rotate-180' : ''}`}>
                            expand_more
                        </span>
                    </button>
                    {wsOpen && (
                        <div className="absolute right-0 top-full mt-1 w-52 bg-white border border-border-light rounded-sm shadow-lg z-50 max-h-72 overflow-y-auto">
                            {/* Header */}
                            <div className="flex items-center justify-between px-3 py-1.5 border-b border-border-light">
                                <span className="text-[10px] font-semibold text-text-sub uppercase tracking-wide">Filter WS = No</span>
                                {wsCount > 0 && (
                                    <button
                                        onClick={() => dispatch({ type: 'CLEAR_WS_FILTER' })}
                                        className="text-[10px] text-primary hover:text-primary/80 font-medium"
                                    >
                                        Clear
                                    </button>
                                )}
                            </div>
                            {visibleCriteria.length === 0 && (
                                <div className="px-3 py-2 text-[11px] text-text-sub">
                                    Enable L1 or L2 to see criteria.
                                </div>
                            )}
                            {visibleCriteria.map(({ group, items }) => (
                                <div key={group}>
                                    <div className="px-3 pt-2 pb-1 text-[9px] font-bold text-text-sub uppercase tracking-wider">
                                        {group}
                                    </div>
                                    {items.map((ws) => (
                                        <label
                                            key={ws.key}
                                            className="flex items-center gap-2 px-3 py-1 hover:bg-surface-light cursor-pointer"
                                        >
                                            <input
                                                type="checkbox"
                                                checked={state.wsFilter.has(ws.key)}
                                                onChange={() => dispatch({ type: 'TOGGLE_WS_FILTER', payload: ws.key })}
                                                className="w-3.5 h-3.5 rounded-sm border-border-light text-primary focus:ring-primary/40"
                                            />
                                            <span className="text-xs text-text-main">{ws.label}</span>
                                        </label>
                                    ))}
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Has Similar toggle */}
                <button
                    type="button"
                    aria-label="Filter controls with similar controls"
                    title="Show only controls that have similar controls"
                    onClick={() => dispatch({ type: 'TOGGLE_HAS_SIMILAR' })}
                    className={`h-8 px-2.5 text-[10px] uppercase font-semibold tracking-wide rounded-sm border transition-colors flex items-center gap-1 flex-shrink-0 ${
                        state.filterHasSimilar
                            ? 'bg-primary text-white border-primary'
                            : 'bg-white text-text-sub border-border-light hover:border-primary/40'
                    }`}
                >
                    <span className="material-symbols-outlined text-[14px]">hub</span>
                    Similar
                </button>

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

            {/* Row 2: Search — requires Enter / button to execute */}
            <div className="flex items-center gap-2">
                <ControlsSearchBar
                    value={state.searchQuery}
                    searchMode={state.searchMode}
                    searchTags={state.searchTags}
                    semanticFeatures={state.semanticFeatures}
                    keywordFields={state.keywordFields}
                    dispatch={dispatch}
                    disabled={searchDisabled}
                    onExecuteSearch={() => dispatch({ type: 'EXECUTE_SEARCH' })}
                />
            </div>
        </div>
    );
};
