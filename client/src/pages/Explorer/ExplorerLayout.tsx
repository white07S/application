import React, { useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useFilterState } from './hooks/useFilterState';
import { FilterSidebar } from './components/FilterSidebar';
import ControlsExplorer from './controls/ControlsExplorer';
import { AppliedSidebarFilters, EMPTY_SIDEBAR_FILTERS } from './controls/types';

const PlaceholderView: React.FC<{ title: string; icon: string }> = ({ title, icon }) => (
    <div className="flex flex-col items-center justify-center h-64 text-text-sub">
        <span className="material-symbols-outlined text-[32px] mb-2">{icon}</span>
        <span className="text-sm font-medium">{title} Explorer</span>
        <span className="text-xs mt-1">Coming soon</span>
    </div>
);

const ExplorerLayout: React.FC = () => {
    const [state, dispatch] = useFilterState();
    const location = useLocation();
    const [appliedFilters, setAppliedFilters] = useState<AppliedSidebarFilters>(EMPTY_SIDEBAR_FILTERS);

    const handleApplyFilters = useCallback(() => {
        setAppliedFilters(prev => ({
            functions: Array.from(state.selectedFunctions),
            locations: Array.from(state.selectedLocations),
            consolidated_entities: Array.from(state.selectedCEs),
            assessment_units: Array.from(state.selectedAUs),
            risk_themes: Array.from(state.selectedRiskThemes),
            filterLogic: prev.filterLogic,
            relationshipScope: prev.relationshipScope,
        }));
    }, [state]);

    const handleFilterLogicChange = useCallback((logic: 'and' | 'or') => {
        setAppliedFilters(prev => ({ ...prev, filterLogic: logic }));
    }, []);

    const handleRelationshipScopeChange = useCallback((scope: 'owns' | 'related' | 'both') => {
        setAppliedFilters(prev => ({ ...prev, relationshipScope: scope }));
    }, []);

    const activeView = location.pathname.includes('/controls') ? 'controls'
        : location.pathname.includes('/events') ? 'events'
        : location.pathname.includes('/issues') ? 'issues'
        : 'controls';

    return (
        <main>
            <div className="w-full max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4">
                <div className="flex">
                    {/* Sticky filter sidebar — fixed height, no page scroll */}
                    <div className="sticky top-12 h-[calc(100vh-48px)] py-4">
                        <FilterSidebar state={state} dispatch={dispatch} onApply={handleApplyFilters} />
                    </div>

                    {/* Content area */}
                    <div className="flex-1 min-w-0 py-4 pl-4 flex flex-col">
                        {activeView === 'controls' && (
                            <ControlsExplorer
                                appliedFilters={appliedFilters}
                                onFilterLogicChange={handleFilterLogicChange}
                                onRelationshipScopeChange={handleRelationshipScopeChange}
                            />
                        )}
                        {activeView === 'events' && <PlaceholderView title="Events" icon="event_note" />}
                        {activeView === 'issues' && <PlaceholderView title="Issues" icon="report_problem" />}
                    </div>
                </div>
            </div>
        </main>
    );
};

export default ExplorerLayout;
