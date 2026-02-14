import { useReducer } from 'react';
import { FilterState, FilterAction } from '../types';

const initialState: FilterState = {
    asOfDate: new Date().toISOString().split('T')[0],
    cascadeEnabled: true,
    selectedFunctions: new Set<string>(),
    selectedLocations: new Set<string>(),
    selectedCEs: new Set<string>(),
    selectedAUs: new Set<string>(),
    selectedRiskThemes: new Set<string>(),
};

function toggleInSet(set: Set<string>, id: string): Set<string> {
    const next = new Set(set);
    if (next.has(id)) {
        next.delete(id);
    } else {
        next.add(id);
    }
    return next;
}

function filterReducer(state: FilterState, action: FilterAction): FilterState {
    switch (action.type) {
        case 'SET_DATE':
            return { ...state, asOfDate: action.payload };
        case 'TOGGLE_CASCADE':
            return { ...state, cascadeEnabled: !state.cascadeEnabled };
        case 'TOGGLE_FUNCTION':
            return { ...state, selectedFunctions: toggleInSet(state.selectedFunctions, action.payload) };
        case 'TOGGLE_LOCATION':
            return { ...state, selectedLocations: toggleInSet(state.selectedLocations, action.payload) };
        case 'TOGGLE_CE':
            return { ...state, selectedCEs: toggleInSet(state.selectedCEs, action.payload) };
        case 'TOGGLE_AU':
            return { ...state, selectedAUs: toggleInSet(state.selectedAUs, action.payload) };
        case 'TOGGLE_RISK_THEME':
            return { ...state, selectedRiskThemes: toggleInSet(state.selectedRiskThemes, action.payload) };
        case 'CLEAR_SECTION':
            return { ...state, [action.payload]: new Set<string>() };
        case 'RESET_ALL':
            return {
                ...initialState,
                asOfDate: new Date().toISOString().split('T')[0],
                cascadeEnabled: state.cascadeEnabled,
                selectedFunctions: new Set<string>(),
                selectedLocations: new Set<string>(),
                selectedCEs: new Set<string>(),
                selectedAUs: new Set<string>(),
                selectedRiskThemes: new Set<string>(),
            };
        default:
            return state;
    }
}

export function getSelectionCount(state: FilterState): number {
    return (
        state.selectedFunctions.size +
        state.selectedLocations.size +
        state.selectedCEs.size +
        state.selectedAUs.size +
        state.selectedRiskThemes.size
    );
}

export function useFilterState() {
    return useReducer(filterReducer, initialState);
}
