import { useReducer, useMemo } from 'react';
import {
    ControlsViewState,
    ControlsAction,
    ControlWithDetails,
    ControlGroup,
    GroupByField,
    SearchMode,
    SemanticFeature,
} from '../types';
import { MOCK_CONTROLS } from '../mockData';

const initialState: ControlsViewState = {
    searchQuery: '',
    searchMode: 'keyword',
    semanticFeatures: new Set<SemanticFeature>([
        'control_title',
        'control_description',
    ]),
    groupBy: 'none',
    filterKeyControl: true,
    filterActiveOnly: true,
    expandedGroups: new Set<string>(),
};

function reducer(state: ControlsViewState, action: ControlsAction): ControlsViewState {
    switch (action.type) {
        case 'SET_SEARCH':
            return { ...state, searchQuery: action.payload };
        case 'SET_SEARCH_MODE':
            return { ...state, searchMode: action.payload };
        case 'TOGGLE_SEMANTIC_FEATURE': {
            const next = new Set(state.semanticFeatures);
            if (next.has(action.payload)) {
                if (next.size > 1) next.delete(action.payload); // keep at least one
            } else {
                next.add(action.payload);
            }
            return { ...state, semanticFeatures: next };
        }
        case 'SET_GROUP_BY':
            return { ...state, groupBy: action.payload, expandedGroups: new Set<string>() };
        case 'TOGGLE_KEY_CONTROL':
            return { ...state, filterKeyControl: !state.filterKeyControl };
        case 'TOGGLE_ACTIVE_ONLY':
            return { ...state, filterActiveOnly: !state.filterActiveOnly };
        case 'TOGGLE_GROUP': {
            const next = new Set(state.expandedGroups);
            if (next.has(action.payload)) {
                next.delete(action.payload);
            } else {
                next.add(action.payload);
            }
            return { ...state, expandedGroups: next };
        }
        default:
            return state;
    }
}

function matchesSearch(c: ControlWithDetails, query: string, mode: SearchMode): boolean {
    if (!query) return true;
    const q = query.toLowerCase();

    if (mode === 'id') {
        return c.control.control_id.toLowerCase().includes(q);
    }

    // keyword, semantic, hybrid all use same client-side filter for now
    return (
        c.control.control_id.toLowerCase().includes(q) ||
        c.control.control_title.toLowerCase().includes(q) ||
        c.control.control_description.toLowerCase().includes(q) ||
        c.control.control_owner.toLowerCase().includes(q)
    );
}

function groupControls(
    controls: ControlWithDetails[],
    groupBy: GroupByField,
): ControlGroup[] {
    if (groupBy === 'none') {
        return [{ key: '__all__', label: 'All Controls', controls }];
    }

    const field = groupBy === 'preventative_detective'
        ? 'preventative_detective'
        : 'manual_automated';

    const map = new Map<string, ControlWithDetails[]>();
    for (const c of controls) {
        const key = c.control[field];
        if (!map.has(key)) map.set(key, []);
        map.get(key)!.push(c);
    }

    return Array.from(map.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, items]) => ({
            key,
            label: key,
            controls: items,
        }));
}

export function useControlsState() {
    const [state, dispatch] = useReducer(reducer, initialState);

    const { groups, totalFiltered, totalAll } = useMemo(() => {
        const all = MOCK_CONTROLS;
        let filtered = all;

        if (state.filterKeyControl) {
            filtered = filtered.filter((c) => c.control.key_control);
        }
        if (state.filterActiveOnly) {
            filtered = filtered.filter((c) => c.control.control_status === 'Active');
        }
        if (state.searchQuery) {
            filtered = filtered.filter((c) => matchesSearch(c, state.searchQuery, state.searchMode));
        }

        const grouped = groupControls(filtered, state.groupBy);

        return {
            groups: grouped,
            totalFiltered: filtered.length,
            totalAll: all.length,
        };
    }, [state.searchQuery, state.searchMode, state.filterKeyControl, state.filterActiveOnly, state.groupBy]);

    return { state, dispatch, groups, totalFiltered, totalAll };
}
