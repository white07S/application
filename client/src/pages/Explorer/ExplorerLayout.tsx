import React, { useState, useCallback } from 'react';
import { useFilterState } from './hooks/useFilterState';
import { FilterSidebar } from './components/FilterSidebar';
import ControlsExplorer from './controls/ControlsExplorer';
import DashboardLayout from './dashboard/DashboardLayout';
import DashboardTabs from './dashboard/components/DashboardTabs';
import type { DashboardTab } from './dashboard/types';
import { AppliedSidebarFilters, EMPTY_SIDEBAR_FILTERS } from './controls/types';

const ExplorerLayout: React.FC = () => {
    const [state, dispatch] = useFilterState();
    const [appliedFilters, setAppliedFilters] = useState<AppliedSidebarFilters>(EMPTY_SIDEBAR_FILTERS);
    const [activeTab, setActiveTab] = useState<DashboardTab>('controls');

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

    return (
        <main>
            <div className="w-full max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4">
                <div className="flex">
                    {/* Sticky filter sidebar */}
                    <div className="sticky top-12 h-[calc(100vh-48px)] py-4">
                        <FilterSidebar state={state} dispatch={dispatch} onApply={handleApplyFilters} />
                    </div>

                    {/* Content area */}
                    <div className="flex-1 min-w-0 py-4 pl-4 flex flex-col">
                        <DashboardTabs activeTab={activeTab} onTabChange={setActiveTab} />

                        {activeTab === 'controls' ? (
                            <ControlsExplorer
                                appliedFilters={appliedFilters}
                                onFilterLogicChange={handleFilterLogicChange}
                                onRelationshipScopeChange={handleRelationshipScopeChange}
                            />
                        ) : (
                            <DashboardLayout activeTab={activeTab} appliedFilters={appliedFilters} />
                        )}
                    </div>
                </div>
            </div>
        </main>
    );
};

export default ExplorerLayout;
