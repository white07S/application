export interface ConnectionStatus {
    connected: boolean;
    url: string;
    database: string;
    error: string | null;
}

export interface TableInfo {
    name: string;
    category: string;
    domain: string;
    record_count: number;
    is_relation: boolean;
}

export interface TableListResponse {
    tables: TableInfo[];
}

export interface PaginatedRecords {
    table_name: string;
    records: Record<string, any>[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
    is_relation: boolean;
    has_embeddings: boolean;
}

export interface RelationshipExpansion {
    edge: Record<string, any>;
    in_record: Record<string, any> | null;
    out_record: Record<string, any> | null;
    in_table: string;
    out_table: string;
}

export interface TableCategory {
    id: string;
    label: string;
    icon: string;
    tables: TableInfo[];
}

/** A domain section containing category sub-groups. */
export interface DomainGroup {
    id: string;
    label: string;
    icon: string;
    totalRecords: number;
    categories: TableCategory[];
}

// View modes for the DevData page
export type ViewMode = 'overview' | 'postgres' | 'qdrant' | 'consistency' | 'snapshots';

// Data domains
export type DataType = 'all' | 'orgs' | 'risks' | 'controls' | 'system';

/** Domain display metadata. */
export const DOMAIN_META: Record<DataType, { label: string; icon: string }> = {
    all: { label: 'All Tables', icon: 'apps' },
    orgs: { label: 'Organizations', icon: 'account_tree' },
    risks: { label: 'Risk Themes', icon: 'warning' },
    controls: { label: 'Controls', icon: 'verified_user' },
    system: { label: 'System', icon: 'settings' },
};

/** Domains that support Qdrant and Consistency tabs. */
export const DOMAINS_WITH_QDRANT: DataType[] = ['all', 'controls'];

/** Domain display order. */
const DOMAIN_ORDER: DataType[] = ['orgs', 'risks', 'controls', 'system'];

/** Known category display metadata. */
const KNOWN_CATEGORIES: Record<string, { label: string; icon: string }> = {
    reference: { label: 'Reference', icon: 'menu_book' },
    main: { label: 'Main', icon: 'table_chart' },
    relation: { label: 'Relations', icon: 'share' },
    model: { label: 'Models', icon: 'psychology' },
    version: { label: 'Versions', icon: 'history' },
    other: { label: 'Other', icon: 'folder' },
};

/** Get display metadata for a category. */
export function getCategoryMeta(categoryId: string): { label: string; icon: string } {
    if (KNOWN_CATEGORIES[categoryId]) {
        return KNOWN_CATEGORIES[categoryId];
    }
    const label = categoryId
        .split('_')
        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
        .join(' ');
    return { label, icon: 'folder' };
}

/**
 * Group tables by category within a flat list.
 * Returns categories in a stable order (known categories first, then alphabetical).
 */
export function groupTablesByCategory(tables: TableInfo[]): TableCategory[] {
    const groups: Record<string, TableInfo[]> = {};
    for (const table of tables) {
        const cat = table.category || 'other';
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(table);
    }

    const knownOrder = ['reference', 'main', 'relation', 'model', 'version', 'other'];
    const result: TableCategory[] = [];
    const seen = new Set<string>();

    for (const catId of knownOrder) {
        if (groups[catId]) {
            result.push({ id: catId, ...getCategoryMeta(catId), tables: groups[catId] });
            seen.add(catId);
        }
    }
    for (const catId of Object.keys(groups).sort()) {
        if (!seen.has(catId)) {
            result.push({ id: catId, ...getCategoryMeta(catId), tables: groups[catId] });
        }
    }
    return result;
}

/**
 * Group tables by domain, then by category within each domain.
 * When selectedDomain != 'all', only returns tables for that domain.
 */
export function groupTablesByDomain(tables: TableInfo[], selectedDomain: DataType): DomainGroup[] {
    // Filter by selected domain
    const filtered = selectedDomain === 'all' ? tables : tables.filter(t => t.domain === selectedDomain);

    // Group by domain
    const byDomain: Record<string, TableInfo[]> = {};
    for (const table of filtered) {
        const d = table.domain || 'system';
        if (!byDomain[d]) byDomain[d] = [];
        byDomain[d].push(table);
    }

    const result: DomainGroup[] = [];
    const order = selectedDomain === 'all' ? DOMAIN_ORDER : [selectedDomain];

    for (const domainId of order) {
        const domainTables = byDomain[domainId];
        if (!domainTables || domainTables.length === 0) continue;
        const meta = DOMAIN_META[domainId as DataType] || { label: domainId, icon: 'folder' };
        const totalRecords = domainTables.reduce((sum, t) => sum + Math.max(0, t.record_count), 0);
        result.push({
            id: domainId,
            label: meta.label,
            icon: meta.icon,
            totalRecords,
            categories: groupTablesByCategory(domainTables),
        });
    }

    return result;
}
