import React from 'react';
import { useControlsState } from './hooks/useControlsState';
import { ControlsToolbar } from './components/ControlsToolbar';
import { ActiveFilters } from './components/ActiveFilters';
import { ControlsList } from './components/ControlsList';
import { AppliedSidebarFilters } from './types';

interface ControlsExplorerProps {
    appliedFilters: AppliedSidebarFilters;
    onFilterLogicChange: (logic: 'and' | 'or') => void;
    onRelationshipScopeChange: (scope: 'owns' | 'related' | 'both') => void;
}

const ControlsExplorer: React.FC<ControlsExplorerProps> = ({
    appliedFilters,
    onFilterLogicChange,
    onRelationshipScopeChange,
}) => {
    const {
        state, dispatch, groups, totalFiltered, totalAll,
        loadMore, loading, loadingMore, hasMore,
    } = useControlsState(appliedFilters);

    return (
        <div className="flex flex-col gap-0 h-full">
            {/* Toolbar: range + search + group-by */}
            <ControlsToolbar state={state} dispatch={dispatch} />

            {/* Active filter chips + count */}
            <ActiveFilters
                filterKeyControl={state.filterKeyControl}
                filterActiveOnly={state.filterActiveOnly}
                filterLevel1={state.filterLevel1}
                filterLevel2={state.filterLevel2}
                onToggleKeyControl={() => dispatch({ type: 'TOGGLE_KEY_CONTROL' })}
                onToggleActiveOnly={() => dispatch({ type: 'TOGGLE_ACTIVE_ONLY' })}
                onToggleLevel1={() => dispatch({ type: 'TOGGLE_LEVEL_1' })}
                onToggleLevel2={() => dispatch({ type: 'TOGGLE_LEVEL_2' })}
                totalFiltered={totalFiltered}
                totalAll={totalAll}
                filterLogic={appliedFilters.filterLogic}
                relationshipScope={appliedFilters.relationshipScope}
                onFilterLogicChange={onFilterLogicChange}
                onRelationshipScopeChange={onRelationshipScopeChange}
            />

            {/* Controls list */}
            <div className="flex-1 min-h-0 overflow-y-auto pb-6">
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-16 text-text-sub">
                        <div className="animate-spin rounded-full h-6 w-6 border-2 border-primary border-t-transparent mb-3" />
                        <span className="text-sm font-medium">Loading controls...</span>
                    </div>
                ) : state.error ? (
                    <div className="flex flex-col items-center justify-center py-16 text-red-500">
                        <span className="material-symbols-outlined text-[32px] mb-2">error</span>
                        <span className="text-sm font-medium">Error loading controls</span>
                        <span className="text-xs mt-1">{state.error}</span>
                    </div>
                ) : (
                    <ControlsList
                        groups={groups}
                        expandedGroups={state.expandedGroups}
                        onToggleGroup={(key) => dispatch({ type: 'TOGGLE_GROUP', payload: key })}
                        isGrouped={state.groupBy !== 'none'}
                        hasMore={hasMore}
                        loadingMore={loadingMore}
                        onLoadMore={loadMore}
                    />
                )}
            </div>
        </div>
    );
};

export default ControlsExplorer;
