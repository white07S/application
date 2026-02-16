import React from 'react';
import { useControlsState } from './hooks/useControlsState';
import { ControlsToolbar } from './components/ControlsToolbar';
import { ActiveFilters } from './components/ActiveFilters';
import { ControlsList } from './components/ControlsList';

const ControlsExplorer: React.FC = () => {
    const { state, dispatch, groups, totalFiltered, totalAll } = useControlsState();

    return (
        <div className="flex flex-col gap-0 h-full">
            {/* Toolbar: search + group-by + view toggle */}
            <ControlsToolbar state={state} dispatch={dispatch} />

            {/* Active filter chips + count */}
            <ActiveFilters
                filterKeyControl={state.filterKeyControl}
                filterActiveOnly={state.filterActiveOnly}
                onToggleKeyControl={() => dispatch({ type: 'TOGGLE_KEY_CONTROL' })}
                onToggleActiveOnly={() => dispatch({ type: 'TOGGLE_ACTIVE_ONLY' })}
                totalFiltered={totalFiltered}
                totalAll={totalAll}
            />

            {/* Controls list */}
            <div className="flex-1 min-h-0 overflow-y-auto pb-6">
                <ControlsList
                    groups={groups}
                    expandedGroups={state.expandedGroups}
                    onToggleGroup={(key) => dispatch({ type: 'TOGGLE_GROUP', payload: key })}
                    isGrouped={state.groupBy !== 'none'}
                />
            </div>
        </div>
    );
};

export default ControlsExplorer;
