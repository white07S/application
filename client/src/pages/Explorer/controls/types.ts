import type { ApiControlWithDetails } from '../api/explorerApi';

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
    control_created_on: string;
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

export interface SimilarControl {
    control_id: string;
    score: number;
    rank: number;
    category?: string | null; // "near_duplicate" or "weak_similar"
}

export interface AIEnrichment {
    type: 'L1' | 'L2';
    criteria: Record<string, AICriterion>;
    linked_control_ids: string[];
}

export interface ParentL1Score {
    controlId: string;
    criteria: { key: string; yes_no: boolean }[];
    yesCount: number;
    total: number;
}

export interface ControlWithDetails {
    control: Control;
    relationships: ControlRelationships;
    ai: AIEnrichment;
    parentL1Score: ParentL1Score | null;
    similarControls: SimilarControl[];
    searchScore?: number | null;
}

// UI state
export type SearchMode = 'id' | 'keyword' | 'semantic' | 'hybrid';
export type GroupByField = 'none' | 'preventative_detective' | 'manual_automated';

/** Embedding features available for semantic/hybrid search (Qdrant vectors) */
export const SEMANTIC_FEATURES = [
    { key: 'what', label: 'What' },
    { key: 'why', label: 'Why' },
    { key: 'where', label: 'Where' },
] as const;

export type SemanticFeature = (typeof SEMANTIC_FEATURES)[number]['key'];

/** Keyword searchable fields (PostgreSQL FTS) */
export const KEYWORD_FIELDS = [
    { key: 'control_title', label: 'Title', group: 'L1' },
    { key: 'control_description', label: 'Description', group: 'L1' },
    { key: 'what', label: 'What', group: 'L1' },
    { key: 'why', label: 'Why', group: 'L1' },
    { key: 'where', label: 'Where', group: 'L1' },
    { key: 'evidence_description', label: 'Evidence', group: 'L2' },
    { key: 'local_functional_information', label: 'Functional Info', group: 'L2' },
] as const;

export type KeywordField = (typeof KEYWORD_FIELDS)[number]['key'];

/** Sidebar filter selections applied to the controls search. */
export interface AppliedSidebarFilters {
    functions: string[];
    locations: string[];
    consolidated_entities: string[];
    assessment_units: string[];
    risk_themes: string[];
    filterLogic: 'and' | 'or';
    relationshipScope: 'owns' | 'related' | 'both';
}

export const EMPTY_SIDEBAR_FILTERS: AppliedSidebarFilters = {
    functions: [],
    locations: [],
    consolidated_entities: [],
    assessment_units: [],
    risk_themes: [],
    filterLogic: 'and',
    relationshipScope: 'both',
};

export type DateField = 'created_on' | 'last_modified_on';

/** Snapshot of search params committed by explicit user action (Enter / Search button). */
export interface CommittedSearch {
    searchQuery: string;
    searchMode: SearchMode;
    searchTags: string[];
    semanticFeatures: string[];
    keywordFields: string[];
}

export interface ControlsViewState {
    searchQuery: string;
    searchMode: SearchMode;
    semanticFeatures: Set<SemanticFeature>;
    keywordFields: Set<KeywordField>;
    groupBy: GroupByField;
    aiScoreMax: number;
    filterKeyControl: boolean;
    filterActiveOnly: boolean;
    filterLevel1: boolean;
    filterLevel2: boolean;
    dateFrom: string;
    dateTo: string;
    dateField: DateField;
    searchTags: string[];
    expandedGroups: Set<string>;
    committedSearch: CommittedSearch | null;
    // Server-driven state
    controls: ControlWithDetails[];
    cursor: string | null;
    hasMore: boolean;
    totalEstimate: number;
    loading: boolean;
    loadingMore: boolean;
    error: string | null;
}

export type ControlsAction =
    | { type: 'SET_SEARCH'; payload: string }
    | { type: 'SET_SEARCH_MODE'; payload: SearchMode }
    | { type: 'TOGGLE_SEMANTIC_FEATURE'; payload: SemanticFeature }
    | { type: 'TOGGLE_KEYWORD_FIELD'; payload: KeywordField }
    | { type: 'SET_GROUP_BY'; payload: GroupByField }
    | { type: 'SET_AI_SCORE_MAX'; payload: number }
    | { type: 'TOGGLE_KEY_CONTROL' }
    | { type: 'TOGGLE_ACTIVE_ONLY' }
    | { type: 'TOGGLE_LEVEL_1' }
    | { type: 'TOGGLE_LEVEL_2' }
    | { type: 'TOGGLE_GROUP'; payload: string }
    | { type: 'SET_DATE_FROM'; payload: string }
    | { type: 'SET_DATE_TO'; payload: string }
    | { type: 'SET_DATE_FIELD'; payload: DateField }
    | { type: 'SET_SEARCH_TAGS'; payload: string[] }
    | { type: 'EXECUTE_SEARCH' }
    | { type: 'CLEAR_SEARCH' }
    // Async fetch actions
    | { type: 'FETCH_START' }
    | { type: 'FETCH_SUCCESS'; payload: { items: ControlWithDetails[]; cursor: string | null; totalEstimate: number; hasMore: boolean } }
    | { type: 'FETCH_ERROR'; payload: string }
    | { type: 'FETCH_MORE_START' }
    | { type: 'FETCH_MORE_SUCCESS'; payload: { items: ControlWithDetails[]; cursor: string | null; hasMore: boolean } }
    | { type: 'RESET_CONTROLS' };

export interface ControlGroup {
    key: string;
    label: string;
    controls: ControlWithDetails[];
}

// ── Control Detail Overlay Types ────────────────────────────────────

/** AI enrichment with _details narrative fields (from detail endpoint). */
export interface AIEnrichmentDetail {
    // yes/no fields (same as AIEnrichment.criteria but with string values)
    what_yes_no: string | null;
    where_yes_no: string | null;
    who_yes_no: string | null;
    when_yes_no: string | null;
    why_yes_no: string | null;
    what_why_yes_no: string | null;
    risk_theme_yes_no: string | null;
    frequency_yes_no: string | null;
    preventative_detective_yes_no: string | null;
    automation_level_yes_no: string | null;
    followup_yes_no: string | null;
    escalation_yes_no: string | null;
    evidence_yes_no: string | null;
    abbreviations_yes_no: string | null;
    // _details narrative fields
    what_details: string | null;
    where_details: string | null;
    who_details: string | null;
    when_details: string | null;
    why_details: string | null;
    what_why_details: string | null;
    risk_theme_details: string | null;
    frequency_details: string | null;
    preventative_detective_details: string | null;
    automation_level_details: string | null;
    followup_details: string | null;
    escalation_details: string | null;
    evidence_details: string | null;
    abbreviations_details: string | null;
    // Summary & narratives
    summary: string | null;
    control_as_event: string | null;
    control_as_issues: string | null;
    // Narrative fields
    roles: string | null;
    process: string | null;
    product: string | null;
    service: string | null;
    // Taxonomy
    primary_risk_theme_id: string | null;
    secondary_risk_theme_id: string | null;
}

/** Extended control detail response from GET /controls/{id}/detail. */
export interface ControlDetailData {
    control: {
        control_id: string;
        control_title: string | null;
        control_description: string | null;
        key_control: boolean | null;
        hierarchy_level: string | null;
        preventative_detective: string | null;
        manual_automated: string | null;
        execution_frequency: string | null;
        four_eyes_check: boolean | null;
        control_status: string | null;
        evidence_description: string | null;
        local_functional_information: string | null;
        last_modified_on: string | null;
        control_created_on: string | null;
        control_owner: string | null;
        control_owner_gpn: string | null;
        sox_relevant: boolean | null;
    };
    relationships: {
        parent: { id: string; name: string | null } | null;
        children: { id: string; name: string | null }[];
        owns_functions: { id: string; name: string | null }[];
        owns_locations: { id: string; name: string | null }[];
        related_functions: { id: string; name: string | null }[];
        related_locations: { id: string; name: string | null }[];
        risk_themes: { id: string; name: string | null }[];
    };
    ai: AIEnrichmentDetail | null;
    parent_l1_score: {
        control_id: string;
        criteria: { key: string; yes_no: boolean }[];
        yes_count: number;
        total: number;
    } | null;
    similar_controls: SimilarControl[];
    // People
    control_delegate: string | null;
    control_delegate_gpn: string | null;
    control_assessor: string | null;
    control_assessor_gpn: string | null;
    control_created_by: string | null;
    control_created_by_gpn: string | null;
    last_control_modification_requested_by: string | null;
    last_control_modification_requested_by_gpn: string | null;
    control_administrator: string[];
    control_administrator_gpn: string[];
    // Compliance
    ccar_relevant: boolean | null;
    bcbs239_relevant: boolean | null;
    sox_rationale: string | null;
    sox_assertions: string[];
}

/** Version summary from GET /controls/{id}/versions. */
export interface ControlVersionSummary {
    tx_from: string;
    tx_to: string | null;
}

/** Material fields snapshot for diff comparison. */
export interface ControlVersionSnapshot {
    tx_from: string;
    parent_control_id: string | null;
    control_status: string | null;
    key_control: boolean | null;
    control_title: string | null;
    control_description: string | null;
    evidence_description: string | null;
    local_functional_information: string | null;
    execution_frequency: string | null;
    preventative_detective: string | null;
    manual_automated: string | null;
    control_administrator: string[];
    control_owner: string | null;
    control_owner_gpn: string | null;
    last_modified_on: string | null;
}

/** Diff response from POST /controls/{id}/diff. */
export interface ControlDiffData {
    from_version: ControlVersionSnapshot;
    to_version: ControlVersionSnapshot;
}

/** Brief control info for linked-control expansion. */
export interface ControlBrief {
    control_id: string;
    control_title: string | null;
    control_description: string | null;
    hierarchy_level: string | null;
    control_status: string | null;
}

/** Map server API response to client ControlWithDetails type. */
export function mapApiControl(api: ApiControlWithDetails): ControlWithDetails {
    const c = api.control;
    const r = api.relationships;
    const ai = api.ai;

    // Determine L1/L2 type from hierarchy_level
    const level = c.hierarchy_level;
    const aiType: 'L1' | 'L2' = level === 'Level 2' ? 'L2' : 'L1';

    // Build criteria record from AI enrichment — only the level-specific set
    // L1: 7 W-criteria → X/7
    // L2: 7 operational criteria → displayed as X/14 with parent's 7 added at render time
    const criteria: Record<string, AICriterion> = {};
    if (ai) {
        const keys = aiType === 'L1'
            ? ['what', 'where', 'who', 'when', 'why', 'what_why', 'risk_theme']
            : ['frequency', 'preventative_detective', 'automation_level', 'followup', 'escalation', 'evidence', 'abbreviations'];
        for (const key of keys) {
            const yesNoKey = `${key}_yes_no` as keyof typeof ai;
            criteria[key] = {
                yes_no: (ai[yesNoKey] as string || '').toLowerCase() === 'yes',
                detail: '',
            };
        }
    }

    return {
        control: {
            control_id: c.control_id,
            control_title: c.control_title || '',
            control_description: c.control_description || '',
            key_control: c.key_control ?? false,
            hierarchy_level: level === 'Level 2' ? 'L2' : 'L1',
            preventative_detective: c.preventative_detective || '',
            manual_automated: c.manual_automated || '',
            execution_frequency: c.execution_frequency || '',
            control_status: c.control_status || '',
            control_owner: c.control_owner || '',
            valid_from: c.last_modified_on || '',
            control_created_on: c.control_created_on || '',
            sox_relevant: c.sox_relevant ?? false,
        },
        relationships: {
            owning_function: r.owns_functions[0]
                ? { id: r.owns_functions[0].id, label: r.owns_functions[0].name || r.owns_functions[0].id }
                : null,
            owning_location: r.owns_locations[0]
                ? { id: r.owns_locations[0].id, label: r.owns_locations[0].name || r.owns_locations[0].id }
                : null,
            related_functions: r.related_functions.map(f => ({ id: f.id, label: f.name || f.id })),
            related_locations: r.related_locations.map(l => ({ id: l.id, label: l.name || l.id })),
            parent_control_id: r.parent?.id || null,
            child_control_ids: r.children.map(c => c.id),
            risk_themes: r.risk_themes.map(t => ({ id: t.id, name: t.name || t.id, taxonomy: '' })),
        },
        ai: {
            type: aiType,
            criteria,
            linked_control_ids: [],
        },
        parentL1Score: api.parent_l1_score
            ? {
                controlId: api.parent_l1_score.control_id,
                criteria: api.parent_l1_score.criteria,
                yesCount: api.parent_l1_score.yes_count,
                total: api.parent_l1_score.total,
            }
            : null,
        similarControls: (api.similar_controls || []).map(sc => ({
            control_id: sc.control_id,
            score: sc.score,
            rank: sc.rank,
            category: sc.category,
        })),
        searchScore: api.search_score,
    };
}
