import { useReducer, useMemo, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../../../../auth/useAuth';
import { searchControls, ControlsSearchParams } from '../../api/explorerApi';
import {
    ControlsViewState,
    ControlsAction,
    ControlWithDetails,
    ControlGroup,
    GroupByField,
    SemanticFeature,
    DateField,
    AppliedSidebarFilters,
    EMPTY_SIDEBAR_FILTERS,
    mapApiControl,
} from '../types';

const initialState: ControlsViewState = {
    searchQuery: '',
    searchMode: 'keyword',
    semanticFeatures: new Set<SemanticFeature>([
        'control_title',
        'control_description',
    ]),
    groupBy: 'none',
    aiScoreMax: 14,
    filterKeyControl: false,
    filterActiveOnly: false,
    filterLevel1: true,
    filterLevel2: true,
    dateFrom: '',
    dateTo: '',
    dateField: 'created_on' as DateField,
    searchTags: [],
    expandedGroups: new Set<string>(),
    // Server-driven state
    controls: [],
    cursor: null,
    hasMore: false,
    totalEstimate: 0,
    loading: false,
    loadingMore: false,
    error: null,
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
                if (next.size > 1) next.delete(action.payload);
            } else {
                next.add(action.payload);
            }
            return { ...state, semanticFeatures: next };
        }
        case 'SET_GROUP_BY':
            return { ...state, groupBy: action.payload, expandedGroups: new Set<string>() };
        case 'SET_AI_SCORE_MAX': {
            const capped = Math.min(14, Math.max(1, action.payload));
            return { ...state, aiScoreMax: capped };
        }
        case 'TOGGLE_KEY_CONTROL':
            return { ...state, filterKeyControl: !state.filterKeyControl };
        case 'TOGGLE_ACTIVE_ONLY':
            return { ...state, filterActiveOnly: !state.filterActiveOnly };
        case 'TOGGLE_LEVEL_1':
            return { ...state, filterLevel1: !state.filterLevel1 };
        case 'TOGGLE_LEVEL_2':
            return { ...state, filterLevel2: !state.filterLevel2 };
        case 'TOGGLE_GROUP': {
            const next = new Set(state.expandedGroups);
            if (next.has(action.payload)) {
                next.delete(action.payload);
            } else {
                next.add(action.payload);
            }
            return { ...state, expandedGroups: next };
        }
        case 'SET_DATE_FROM':
            return { ...state, dateFrom: action.payload };
        case 'SET_DATE_TO':
            return { ...state, dateTo: action.payload };
        case 'SET_DATE_FIELD':
            return { ...state, dateField: action.payload };
        case 'SET_SEARCH_TAGS':
            return { ...state, searchTags: action.payload, searchQuery: action.payload.join(' ') };
        // Async fetch actions
        case 'FETCH_START':
            return { ...state, loading: true, error: null };
        case 'FETCH_SUCCESS':
            return {
                ...state,
                loading: false,
                controls: action.payload.items,
                cursor: action.payload.cursor,
                totalEstimate: action.payload.totalEstimate,
                hasMore: action.payload.hasMore,
                error: null,
            };
        case 'FETCH_ERROR':
            return { ...state, loading: false, loadingMore: false, error: action.payload };
        case 'FETCH_MORE_START':
            return { ...state, loadingMore: true };
        case 'FETCH_MORE_SUCCESS':
            return {
                ...state,
                loadingMore: false,
                controls: [...state.controls, ...action.payload.items],
                cursor: action.payload.cursor,
                hasMore: action.payload.hasMore,
            };
        case 'RESET_CONTROLS':
            return {
                ...state,
                controls: [],
                cursor: null,
                hasMore: false,
                totalEstimate: 0,
                loading: false,
                loadingMore: false,
                error: null,
            };
        default:
            return state;
    }
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
        const key = c.control[field] || 'Unknown';
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

/** Build the server request params from the current state + applied sidebar filters. */
function buildSearchParams(
    state: ControlsViewState,
    appliedFilters: AppliedSidebarFilters,
    cursor: string | null,
): ControlsSearchParams {
    const params: ControlsSearchParams = {
        page_size: 50,
        cursor: cursor ?? undefined,
    };

    // Sidebar filters
    const hasSidebar =
        appliedFilters.functions.length > 0 ||
        appliedFilters.locations.length > 0 ||
        appliedFilters.consolidated_entities.length > 0 ||
        appliedFilters.assessment_units.length > 0 ||
        appliedFilters.risk_themes.length > 0;

    if (hasSidebar) {
        params.sidebar = {
            functions: appliedFilters.functions,
            locations: appliedFilters.locations,
            consolidated_entities: appliedFilters.consolidated_entities,
            assessment_units: appliedFilters.assessment_units,
            risk_themes: appliedFilters.risk_themes,
        };
        params.filter_logic = appliedFilters.filterLogic;
        params.relationship_scope = appliedFilters.relationshipScope;
    }

    // Search
    if (state.searchQuery.trim()) {
        params.search_query = state.searchQuery.trim();
        params.search_mode = state.searchMode;
        params.search_fields = Array.from(state.semanticFeatures);
    }

    // Toolbar filters
    const toolbar: ControlsSearchParams['toolbar'] = {
        active_only: state.filterActiveOnly,
        key_control: state.filterKeyControl ? true : null,
        level1: state.filterLevel1,
        level2: state.filterLevel2,
        ai_score_max: state.aiScoreMax < 14 ? state.aiScoreMax : null,
        date_from: state.dateFrom || null,
        date_to: state.dateTo ? `${state.dateTo}T23:59:59` : null,
        date_field: state.dateField,
    };
    params.toolbar = toolbar;

    return params;
}

export function useControlsState(appliedFilters: AppliedSidebarFilters = EMPTY_SIDEBAR_FILTERS) {
    const [state, dispatch] = useReducer(reducer, initialState);
    const { getApiAccessToken } = useAuth();
    const abortRef = useRef<AbortController | null>(null);
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Build a dependency key from params that should trigger a new fetch
    const searchDepsKey = JSON.stringify({
        q: state.searchQuery,
        mode: state.searchMode,
        features: Array.from(state.semanticFeatures).sort(),
        keyControl: state.filterKeyControl,
        activeOnly: state.filterActiveOnly,
        level1: state.filterLevel1,
        level2: state.filterLevel2,
        aiScore: state.aiScoreMax,
        dateFrom: state.dateFrom,
        dateTo: state.dateTo,
        dateField: state.dateField,
        filters: appliedFilters,
    });

    // Fetch on param changes (debounced)
    useEffect(() => {
        // Cancel previous request
        if (abortRef.current) abortRef.current.abort();
        if (debounceRef.current) clearTimeout(debounceRef.current);

        dispatch({ type: 'RESET_CONTROLS' });

        debounceRef.current = setTimeout(async () => {
            const controller = new AbortController();
            abortRef.current = controller;

            dispatch({ type: 'FETCH_START' });
            try {
                const token = await getApiAccessToken();
                if (!token || controller.signal.aborted) return;

                const params = buildSearchParams(state, appliedFilters, null);
                const resp = await searchControls(token, params, controller.signal);

                if (controller.signal.aborted) return;
                dispatch({
                    type: 'FETCH_SUCCESS',
                    payload: {
                        items: resp.items.map(mapApiControl),
                        cursor: resp.cursor,
                        totalEstimate: resp.total_estimate,
                        hasMore: resp.has_more,
                    },
                });
            } catch (err: any) {
                if (err?.name === 'AbortError') return;
                dispatch({ type: 'FETCH_ERROR', payload: err?.message || 'Failed to fetch controls' });
            }
        }, 300);

        return () => {
            if (abortRef.current) abortRef.current.abort();
            if (debounceRef.current) clearTimeout(debounceRef.current);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchDepsKey]);

    // Load more (infinite scroll)
    const loadMore = useCallback(async () => {
        if (state.loadingMore || !state.hasMore || !state.cursor) return;

        dispatch({ type: 'FETCH_MORE_START' });
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const params = buildSearchParams(state, appliedFilters, state.cursor);
            const resp = await searchControls(token, params);

            dispatch({
                type: 'FETCH_MORE_SUCCESS',
                payload: {
                    items: resp.items.map(mapApiControl),
                    cursor: resp.cursor,
                    hasMore: resp.has_more,
                },
            });
        } catch (err: any) {
            if (err?.name === 'AbortError') return;
            dispatch({ type: 'FETCH_ERROR', payload: err?.message || 'Failed to load more' });
        }
    }, [state.loadingMore, state.hasMore, state.cursor, appliedFilters, getApiAccessToken, state]);

    // Group controls (client-side)
    const { groups, totalFiltered, totalAll } = useMemo(() => {
        const grouped = groupControls(state.controls, state.groupBy);
        return {
            groups: grouped,
            totalFiltered: state.controls.length,
            totalAll: state.totalEstimate,
        };
    }, [state.controls, state.groupBy, state.totalEstimate]);

    return {
        state,
        dispatch,
        groups,
        totalFiltered,
        totalAll,
        loadMore,
        loading: state.loading,
        loadingMore: state.loadingMore,
        hasMore: state.hasMore,
    };
}
