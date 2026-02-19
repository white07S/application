export interface TreeNode {
    id: string;
    label: string;
    children?: TreeNode[];
    level: number;
    has_children?: boolean;
    childrenLoaded?: boolean;
    node_type?: string;
    status?: string;
    path?: string;
}

export interface FlatItem {
    id: string;
    label: string;
    description?: string;
    function_node_id?: string;
    location_node_id?: string;
    location_type?: string;
}

export interface RiskTaxonomy {
    id: string;
    name: string;
    themes: { id: string; name: string }[];
}

export interface FilterState {
    cascadeEnabled: boolean;
    selectedFunctions: Set<string>;
    selectedLocations: Set<string>;
    selectedCEs: Set<string>;
    selectedAUs: Set<string>;
    selectedRiskThemes: Set<string>;
}

export type FilterAction =
    | { type: 'TOGGLE_CASCADE' }
    | { type: 'TOGGLE_FUNCTION'; payload: string }
    | { type: 'TOGGLE_LOCATION'; payload: string }
    | { type: 'TOGGLE_CE'; payload: string }
    | { type: 'TOGGLE_AU'; payload: string }
    | { type: 'TOGGLE_RISK_THEME'; payload: string }
    | { type: 'SELECT_MANY'; payload: { section: 'selectedFunctions' | 'selectedLocations' | 'selectedCEs' | 'selectedAUs' | 'selectedRiskThemes'; ids: string[] } }
    | { type: 'CLEAR_SECTION'; payload: 'selectedFunctions' | 'selectedLocations' | 'selectedCEs' | 'selectedAUs' | 'selectedRiskThemes' }
    | { type: 'RESET_ALL' };
