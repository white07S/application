import React, { useMemo } from 'react';
import { FilterState, FilterAction, TreeNode, FlatItem, RiskTaxonomy } from '../types';
import { getSelectionCount } from '../hooks/useFilterState';
import { useFunctionTree } from '../hooks/useFunctionTree';
import { useLocationTree } from '../hooks/useLocationTree';
import { useCESearch } from '../hooks/useCESearch';
import { useFilterData } from '../hooks/useFilterData';
import { FilterSection } from './FilterSection';
import { DateFilter } from './DateFilter';
import { HierarchyFilter } from './HierarchyFilter';
import { FlatListFilter } from './FlatListFilter';
import { RiskThemeFilter } from './RiskThemeFilter';
import { FilterChips } from './FilterChips';

interface FilterSidebarProps {
    state: FilterState;
    dispatch: React.Dispatch<FilterAction>;
}

function collectChips(
    state: FilterState,
    functions: TreeNode[],
    locations: TreeNode[],
    ces: FlatItem[],
    aus: FlatItem[],
    taxonomies: RiskTaxonomy[]
) {
    const chips: { id: string; label: string; section: string }[] = [];

    const findLabel = (nodes: TreeNode[], id: string): string | null => {
        for (const n of nodes) {
            if (n.id === id) return n.label;
            if (n.children) {
                const found = findLabel(n.children, id);
                if (found) return found;
            }
        }
        return null;
    };

    state.selectedFunctions.forEach((id) => {
        const label = findLabel(functions, id);
        if (label) chips.push({ id, label, section: 'function' });
    });

    state.selectedLocations.forEach((id) => {
        const label = findLabel(locations, id);
        if (label) chips.push({ id, label, section: 'location' });
    });

    state.selectedCEs.forEach((id) => {
        const item = ces.find((c) => c.id === id);
        if (item) chips.push({ id, label: item.label, section: 'ce' });
    });

    state.selectedAUs.forEach((id) => {
        const item = aus.find((a) => a.id === id);
        if (item) chips.push({ id, label: item.label, section: 'au' });
    });

    state.selectedRiskThemes.forEach((id) => {
        for (const tax of taxonomies) {
            const theme = tax.themes.find((t) => t.id === id);
            if (theme) {
                chips.push({ id, label: theme.name, section: 'risk' });
                break;
            }
        }
    });

    return chips;
}

export const FilterSidebar: React.FC<FilterSidebarProps> = ({ state, dispatch }) => {
    const totalCount = getSelectionCount(state);

    // Data hooks
    const funcTree = useFunctionTree(state.asOfDate);
    const locTree = useLocationTree(state.asOfDate);
    const ceSearch = useCESearch(state.asOfDate);
    const { aus, riskThemes } = useFilterData(state.asOfDate);

    // Collect date warning from any hook that reports a date fallback
    const dateWarning = funcTree.dateWarning || locTree.dateWarning || ceSearch.dateWarning || aus.dateWarning || riskThemes.dateWarning || null;

    const chips = useMemo(
        () => collectChips(state, funcTree.nodes, locTree.nodes, ceSearch.items, aus.items, riskThemes.taxonomies),
        [state, funcTree.nodes, locTree.nodes, ceSearch.items, aus.items, riskThemes.taxonomies]
    );

    const handleRemoveChip = (chip: { id: string; section: string }) => {
        const actionMap: Record<string, FilterAction['type']> = {
            function: 'TOGGLE_FUNCTION',
            location: 'TOGGLE_LOCATION',
            ce: 'TOGGLE_CE',
            au: 'TOGGLE_AU',
            risk: 'TOGGLE_RISK_THEME',
        };
        const type = actionMap[chip.section];
        if (type) dispatch({ type, payload: chip.id } as FilterAction);
    };

    const handleApply = () => {
        console.log('Apply filters:', {
            asOfDate: state.asOfDate,
            cascadeEnabled: state.cascadeEnabled,
            functions: Array.from(state.selectedFunctions),
            locations: Array.from(state.selectedLocations),
            ces: Array.from(state.selectedCEs),
            aus: Array.from(state.selectedAUs),
            riskThemes: Array.from(state.selectedRiskThemes),
        });
    };

    return (
        <div className="w-72 shrink-0 pr-4 border-r border-border-light flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between pb-2 border-b border-border-light">
                <div className="flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[16px] text-text-sub">
                        filter_list
                    </span>
                    <span className="text-md font-semibold text-text-main">Filters</span>
                    {totalCount > 0 && (
                        <span className="bg-primary text-white text-[10px] font-semibold px-1.5 py-0.5 rounded-sm min-w-[18px] text-center">
                            {totalCount}
                        </span>
                    )}
                </div>
                {totalCount > 0 && (
                    <button
                        onClick={() => dispatch({ type: 'RESET_ALL' })}
                        className="text-[10px] text-text-sub hover:text-primary font-medium"
                    >
                        Reset all
                    </button>
                )}
            </div>

            {/* Cascade Toggle */}
            <div className="flex items-center justify-between py-2 border-b border-border-light">
                <div className="flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[14px] text-text-sub">
                        {state.cascadeEnabled ? 'link' : 'link_off'}
                    </span>
                    <span className="text-[10px] font-medium text-text-sub">
                        Cascade filters
                    </span>
                </div>
                <button
                    onClick={() => dispatch({ type: 'TOGGLE_CASCADE' })}
                    className={`relative w-7 h-4 rounded-full transition-colors ${state.cascadeEnabled ? 'bg-primary' : 'bg-gray-300'}`}
                >
                    <span
                        className={`absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform shadow-sm ${state.cascadeEnabled ? 'translate-x-3' : ''}`}
                    />
                </button>
            </div>

            {/* Date Warning */}
            {dateWarning && (
                <div className="flex items-start gap-1.5 px-2 py-1.5 bg-amber-50 border-b border-amber-200">
                    <span className="material-symbols-outlined text-[14px] text-amber-600 mt-0.5 flex-shrink-0">
                        info
                    </span>
                    <span className="text-[10px] text-amber-800 leading-tight">
                        {dateWarning}
                    </span>
                </div>
            )}

            {/* Chips */}
            <FilterChips chips={chips} onRemove={handleRemoveChip} />

            {/* Scrollable filter sections — min-h-0 allows flex child to shrink and scroll */}
            <div className="flex-1 min-h-0 overflow-y-auto divide-y divide-border-light">
                {/* As of Date */}
                <FilterSection
                    icon="calendar_today"
                    title="As of Date"
                    count={0}
                    onClear={() => dispatch({ type: 'SET_DATE', payload: new Date().toISOString().split('T')[0] })}
                    defaultExpanded
                >
                    <DateFilter
                        value={state.asOfDate}
                        onChange={(date) => dispatch({ type: 'SET_DATE', payload: date })}
                    />
                </FilterSection>

                {/* Functions */}
                <FilterSection
                    icon="account_tree"
                    title="Functions"
                    count={state.selectedFunctions.size}
                    onClear={() => dispatch({ type: 'CLEAR_SECTION', payload: 'selectedFunctions' })}
                    loading={funcTree.loading}
                    defaultExpanded
                >
                    <HierarchyFilter
                        nodes={funcTree.nodes}
                        selected={state.selectedFunctions}
                        onToggle={(id) => dispatch({ type: 'TOGGLE_FUNCTION', payload: id })}
                        onExpand={funcTree.loadChildren}
                        onSearchChange={funcTree.onSearchChange}
                        searchLoading={funcTree.searchLoading}
                        loadingNodeId={funcTree.loadingNodeId}
                        loading={funcTree.loading}
                        placeholder="Search functions..."
                    />
                </FilterSection>

                {/* Locations */}
                <FilterSection
                    icon="location_on"
                    title="Locations"
                    count={state.selectedLocations.size}
                    onClear={() => dispatch({ type: 'CLEAR_SECTION', payload: 'selectedLocations' })}
                    loading={locTree.loading}
                >
                    <HierarchyFilter
                        nodes={locTree.nodes}
                        selected={state.selectedLocations}
                        onToggle={(id) => dispatch({ type: 'TOGGLE_LOCATION', payload: id })}
                        onExpand={locTree.loadChildren}
                        onSearchChange={locTree.onSearchChange}
                        searchLoading={locTree.searchLoading}
                        loadingNodeId={locTree.loadingNodeId}
                        loading={locTree.loading}
                        placeholder="Search locations..."
                    />
                </FilterSection>

                {/* Consolidated Entities */}
                <FilterSection
                    icon="corporate_fare"
                    title="Consolidated Entities"
                    count={state.selectedCEs.size}
                    onClear={() => dispatch({ type: 'CLEAR_SECTION', payload: 'selectedCEs' })}
                    loading={ceSearch.loading}
                >
                    <FlatListFilter
                        items={ceSearch.items}
                        selected={state.selectedCEs}
                        onToggle={(id) => dispatch({ type: 'TOGGLE_CE', payload: id })}
                        onSearchChange={ceSearch.setSearch}
                        loading={ceSearch.loading}
                        hasMore={ceSearch.hasMore}
                        placeholder="Search entities..."
                    />
                </FilterSection>

                {/* Assessment Units */}
                <FilterSection
                    icon="assessment"
                    title="Assessment Units"
                    count={state.selectedAUs.size}
                    onClear={() => dispatch({ type: 'CLEAR_SECTION', payload: 'selectedAUs' })}
                    loading={aus.loading}
                >
                    <FlatListFilter
                        items={aus.items}
                        selected={state.selectedAUs}
                        onToggle={(id) => dispatch({ type: 'TOGGLE_AU', payload: id })}
                        loading={aus.loading}
                        placeholder="Search units..."
                    />
                </FilterSection>

                {/* Risk Themes */}
                <FilterSection
                    icon="warning"
                    title="Risk Themes"
                    count={state.selectedRiskThemes.size}
                    onClear={() => dispatch({ type: 'CLEAR_SECTION', payload: 'selectedRiskThemes' })}
                    loading={riskThemes.loading}
                >
                    <RiskThemeFilter
                        taxonomies={riskThemes.taxonomies}
                        selected={state.selectedRiskThemes}
                        onToggle={(id) => dispatch({ type: 'TOGGLE_RISK_THEME', payload: id })}
                    />
                </FilterSection>
            </div>

            {/* Apply Button */}
            <div className="pt-3 pb-1 border-t border-border-light mt-auto">
                <button
                    onClick={handleApply}
                    className="w-full bg-primary text-white py-2 text-sm font-medium hover:bg-primary/90 transition-colors rounded-sm"
                >
                    Apply Filters
                </button>
            </div>
        </div>
    );
};
