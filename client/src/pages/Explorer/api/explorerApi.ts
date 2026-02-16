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
    effective_date?: string | null;
    date_warning?: string | null;
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
    effective_date?: string | null;
    date_warning?: string | null;
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
    effective_date?: string | null;
    date_warning?: string | null;
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

export const fetchFunctions = (token: string, asOfDate: string, parentId?: string, search?: string) =>
    apiFetch<TreeNodesResponse>('/functions', token, {
        as_of_date: asOfDate,
        parent_id: parentId,
        search: search,
    });

export const fetchLocations = (token: string, asOfDate: string, parentId?: string, search?: string) =>
    apiFetch<TreeNodesResponse>('/locations', token, {
        as_of_date: asOfDate,
        parent_id: parentId,
        search: search,
    });

export const fetchCEs = (token: string, asOfDate: string, search?: string, page?: number) =>
    apiFetch<FlatItemsResponse>('/consolidated-entities', token, {
        as_of_date: asOfDate,
        search: search,
        page: page ? String(page) : undefined,
    });

export const fetchAUs = (token: string, asOfDate: string) =>
    apiFetch<FlatItemsResponse>('/assessment-units', token, {
        as_of_date: asOfDate,
    });

export const fetchRiskThemes = (token: string, asOfDate: string) =>
    apiFetch<RiskTaxonomiesResponse>('/risk-themes', token, {
        as_of_date: asOfDate,
    });
