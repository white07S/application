import { appConfig } from '../../../config/appConfig';

const BASE = `${appConfig.api.baseUrl}/api/v2/explorer/filters`;

export interface ApiTreeNode {
    id: string;
    label: string;
    level: number;
    has_children: boolean;
    children: ApiTreeNode[];
    node_type?: string | null;
    status?: string | null;
    path?: string | null;
}

export interface TreeNodesResponse {
    nodes: ApiTreeNode[];
}

export interface ApiFlatItem {
    id: string;
    label: string;
    description?: string;
    function_node_id?: string | null;
    location_node_id?: string | null;
    location_type?: string | null;
}

export interface FlatItemsResponse {
    items: ApiFlatItem[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
}

export interface ApiRiskTheme {
    id: string;
    name: string;
}

export interface ApiRiskTaxonomy {
    id: string;
    name: string;
    themes: ApiRiskTheme[];
}

export interface RiskTaxonomiesResponse {
    taxonomies: ApiRiskTaxonomy[];
}

async function apiFetch<T>(path: string, token: string, params?: Record<string, string | undefined>): Promise<T> {
    const url = new URL(`${BASE}${path}`);
    if (params) {
        Object.entries(params).forEach(([k, v]) => {
            if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
        });
    }
    const res = await fetch(url.toString(), {
        headers: { 'X-MS-TOKEN-AAD': token },
    });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    return res.json();
}

export const fetchFunctions = (token: string, parentId?: string, search?: string) =>
    apiFetch<TreeNodesResponse>('/functions', token, {
        parent_id: parentId,
        search: search,
    });

export const fetchLocations = (token: string, parentId?: string, search?: string) =>
    apiFetch<TreeNodesResponse>('/locations', token, {
        parent_id: parentId,
        search: search,
    });

export const fetchCEs = (token: string, search?: string, page?: number) =>
    apiFetch<FlatItemsResponse>('/consolidated-entities', token, {
        search: search,
        page: page ? String(page) : undefined,
    });

export const fetchAUs = (token: string) => apiFetch<FlatItemsResponse>('/assessment-units', token);

export const fetchRiskThemes = (token: string) => apiFetch<RiskTaxonomiesResponse>('/risk-themes', token);

// ──────────────────────────────────────────────────────────────────────
// Controls search API
// ──────────────────────────────────────────────────────────────────────

const CONTROLS_BASE = `${appConfig.api.baseUrl}/api/v2/explorer/controls`;

export interface SidebarFiltersPayload {
    functions: string[];
    locations: string[];
    consolidated_entities: string[];
    assessment_units: string[];
    risk_themes: string[];
}

export interface ToolbarFiltersPayload {
    active_only: boolean;
    key_control: boolean | null;
    level1: boolean;
    level2: boolean;
    ai_score_max: number | null;
    date_from: string | null;
    date_to: string | null;
    date_field: 'created_on' | 'last_modified_on';
}

export interface ControlsSearchParams {
    sidebar?: SidebarFiltersPayload;
    filter_logic?: 'and' | 'or';
    relationship_scope?: 'owns' | 'related' | 'both';
    search_query?: string | null;
    search_mode?: 'keyword' | 'semantic' | 'hybrid' | 'id' | null;
    search_fields?: string[];
    toolbar?: ToolbarFiltersPayload;
    cursor?: string | null;
    page_size?: number;
}

export interface ApiNamedItem {
    id: string;
    name: string | null;
}

export interface ApiControlResponse {
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
}

export interface ApiControlRelationships {
    parent: ApiNamedItem | null;
    children: ApiNamedItem[];
    owns_functions: ApiNamedItem[];
    owns_locations: ApiNamedItem[];
    related_functions: ApiNamedItem[];
    related_locations: ApiNamedItem[];
    risk_themes: ApiNamedItem[];
}

export interface ApiAIEnrichment {
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
    summary: string | null;
    control_as_event: string | null;
    control_as_issues: string | null;
    primary_risk_theme_id: string | null;
    secondary_risk_theme_id: string | null;
}

export interface ApiSimilarControl {
    control_id: string;
    score: number;
    rank: number;
}

export interface ApiParentL1Score {
    control_id: string;
    criteria: { key: string; yes_no: boolean }[];
    yes_count: number;
    total: number;
}

export interface ApiControlWithDetails {
    control: ApiControlResponse;
    relationships: ApiControlRelationships;
    ai: ApiAIEnrichment | null;
    parent_l1_score: ApiParentL1Score | null;
    similar_controls: ApiSimilarControl[];
    search_score: number | null;
}

export interface ControlsSearchResponse {
    items: ApiControlWithDetails[];
    cursor: string | null;
    total_estimate: number;
    has_more: boolean;
}

export async function searchControls(
    token: string,
    params: ControlsSearchParams,
    signal?: AbortSignal,
): Promise<ControlsSearchResponse> {
    const res = await fetch(`${CONTROLS_BASE}/search`, {
        method: 'POST',
        headers: {
            'X-MS-TOKEN-AAD': token,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(params),
        signal,
    });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    return res.json();
}
