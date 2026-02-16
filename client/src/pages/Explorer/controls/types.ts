export interface Control {
    control_id: string;
    control_title: string;
    control_description: string;
    key_control: boolean;
    hierarchy_level: 'L1' | 'L2';
    preventative_detective: string;
    manual_automated: string;
    execution_frequency: string;
    control_status: string;
    control_owner: string;
    valid_from: string;
    sox_relevant: boolean;
}

export interface ControlRelationships {
    owning_function: { id: string; label: string } | null;
    owning_location: { id: string; label: string } | null;
    related_functions: { id: string; label: string }[];
    related_locations: { id: string; label: string }[];
    parent_control_id: string | null;
    child_control_ids: string[];
    risk_themes: { id: string; name: string; taxonomy: string }[];
}

export interface AICriterion {
    yes_no: boolean;
    detail: string;
}

export interface AIEnrichment {
    type: 'L1' | 'L2';
    criteria: Record<string, AICriterion>;
    linked_control_ids: string[];
}

export interface ControlWithDetails {
    control: Control;
    relationships: ControlRelationships;
    ai: AIEnrichment;
}

// UI state
export type SearchMode = 'id' | 'keyword' | 'semantic' | 'hybrid';
export type GroupByField = 'none' | 'preventative_detective' | 'manual_automated';

/** Embedding features available for semantic/hybrid search */
export const SEMANTIC_FEATURES = [
    { key: 'control_title', label: 'Title' },
    { key: 'control_description', label: 'Description' },
    { key: 'evidence_description', label: 'Evidence' },
    { key: 'local_functional_information', label: 'Functional Info' },
    { key: 'control_as_event', label: 'As Event' },
    { key: 'control_as_issues', label: 'As Issues' },
] as const;

export type SemanticFeature = (typeof SEMANTIC_FEATURES)[number]['key'];

export interface ControlsViewState {
    searchQuery: string;
    searchMode: SearchMode;
    semanticFeatures: Set<SemanticFeature>;
    groupBy: GroupByField;
    filterKeyControl: boolean;
    filterActiveOnly: boolean;
    expandedGroups: Set<string>;
}

export type ControlsAction =
    | { type: 'SET_SEARCH'; payload: string }
    | { type: 'SET_SEARCH_MODE'; payload: SearchMode }
    | { type: 'TOGGLE_SEMANTIC_FEATURE'; payload: SemanticFeature }
    | { type: 'SET_GROUP_BY'; payload: GroupByField }
    | { type: 'TOGGLE_KEY_CONTROL' }
    | { type: 'TOGGLE_ACTIVE_ONLY' }
    | { type: 'TOGGLE_GROUP'; payload: string };

export interface ControlGroup {
    key: string;
    label: string;
    controls: ControlWithDetails[];
}
