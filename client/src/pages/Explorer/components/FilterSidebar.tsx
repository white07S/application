import React, { useMemo, useState, useCallback } from 'react';
import { FilterState, FilterAction, TreeNode, FlatItem, RiskTaxonomy } from '../types';
import { getSelectionCount } from '../hooks/useFilterState';
import { useFunctionTree } from '../hooks/useFunctionTree';
import { useLocationTree } from '../hooks/useLocationTree';
import { useCESearch } from '../hooks/useCESearch';
import { useFilterData } from '../hooks/useFilterData';
import { useCascadeSuggestions, CascadeSuggestion } from '../hooks/useCascadeSuggestions';
import { FilterSection } from './FilterSection';
import { HierarchyFilter } from './HierarchyFilter';
import { FlatListFilter } from './FlatListFilter';
import { RiskThemeFilter } from './RiskThemeFilter';
import { FilterChips } from './FilterChips';
import { CascadeBanner } from './CascadeBanner';

interface FilterSidebarProps {
    state: FilterState;
    dispatch: React.Dispatch<FilterAction>;
    onApply?: () => void;
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

export const FilterSidebar: React.FC<FilterSidebarProps> = ({ state, dispatch, onApply }) => {
    const totalCount = getSelectionCount(state);

    // Data hooks
    const funcTree = useFunctionTree();
    const locTree = useLocationTree();
    const ceSearch = useCESearch();
    const { aus, riskThemes } = useFilterData();

    // Cascade suggestions
    const { suggestions, dismiss } = useCascadeSuggestions(
        state,
        aus.items,
        ceSearch.items,
        locTree.nodes,
    );

    // Section expansion state
    const SECTIONS = ['functions', 'locations', 'ces', 'aus', 'risk'] as const;
    const [expanded, setExpanded] = useState<Record<string, boolean>>({
        functions: true,
        locations: false,
        ces: false,
        aus: false,
        risk: false,
    });
    const toggleSection = useCallback((key: string) => {
        setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
    }, []);
    const allCollapsed = SECTIONS.every((k) => !expanded[k]);
    const toggleAll = useCallback(() => {
        const newVal = allCollapsed; // if all collapsed, expand all; otherwise collapse all
        setExpanded(Object.fromEntries(SECTIONS.map((k) => [k, newVal])));
    }, [allCollapsed]);

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

    const handleAcceptSuggestion = (suggestion: CascadeSuggestion) => {
        dispatch({
            type: 'SELECT_MANY',
            payload: { section: suggestion.targetSection, ids: suggestion.suggestedIds },
        });
        dismiss(suggestion);
    };

    // Helper: get banners targeting a specific section
    const bannersFor = (targetSection: CascadeSuggestion['targetSection']) =>
        suggestions.filter((s) => s.targetSection === targetSection);

    const handleApply = () => {
        onApply?.();
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
                <div className="flex items-center gap-1.5">
                    {totalCount > 0 && (
                        <button
                            onClick={() => dispatch({ type: 'RESET_ALL' })}
                            className="flex items-center gap-1 text-[10px] text-text-sub hover:text-primary font-medium border border-border-light rounded px-1.5 py-0.5 transition-colors"
                            title="Reset all filters"
                        >
                            <span className="material-symbols-outlined text-[12px]">restart_alt</span>
                            Reset
                        </button>
                    )}
                    <button
                        onClick={toggleAll}
                        className="flex items-center gap-1 text-[10px] text-text-sub hover:text-primary font-medium border border-border-light rounded px-1.5 py-0.5 transition-colors"
                        title={allCollapsed ? 'Expand all sections' : 'Collapse all sections'}
                    >
                        <span className="material-symbols-outlined text-[12px]">
                            {allCollapsed ? 'unfold_more' : 'unfold_less'}
                        </span>
                        {allCollapsed ? 'Expand' : 'Collapse'}
                    </button>
                </div>
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

            {/* Chips */}
            <FilterChips chips={chips} onRemove={handleRemoveChip} />

            {/* Scrollable filter sections — min-h-0 allows flex child to shrink and scroll */}
            <div className="flex-1 min-h-0 overflow-y-auto divide-y divide-border-light">
                {/* Functions */}
                <FilterSection
                    icon="account_tree"
                    title="Functions"
                    count={state.selectedFunctions.size}
                    onClear={() => dispatch({ type: 'CLEAR_SECTION', payload: 'selectedFunctions' })}
                    loading={funcTree.loading}
                    expanded={expanded.functions}
                    onToggle={() => toggleSection('functions')}
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
                    expanded={expanded.locations}
                    onToggle={() => toggleSection('locations')}
                >
                    {bannersFor('selectedLocations').map((s) => (
                        <CascadeBanner
                            key={`${s.sourceSection}-${s.targetSection}`}
                            suggestion={s}
                            onAccept={() => handleAcceptSuggestion(s)}
                            onDismiss={() => dismiss(s)}
                        />
                    ))}
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
                    expanded={expanded.ces}
                    onToggle={() => toggleSection('ces')}
                >
                    {bannersFor('selectedCEs').map((s) => (
                        <CascadeBanner
                            key={`${s.sourceSection}-${s.targetSection}`}
                            suggestion={s}
                            onAccept={() => handleAcceptSuggestion(s)}
                            onDismiss={() => dismiss(s)}
                        />
                    ))}
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
                    expanded={expanded.aus}
                    onToggle={() => toggleSection('aus')}
                >
                    {bannersFor('selectedAUs').map((s) => (
                        <CascadeBanner
                            key={`${s.sourceSection}-${s.targetSection}`}
                            suggestion={s}
                            onAccept={() => handleAcceptSuggestion(s)}
                            onDismiss={() => dismiss(s)}
                        />
                    ))}
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
                    expanded={expanded.risk}
                    onToggle={() => toggleSection('risk')}
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
