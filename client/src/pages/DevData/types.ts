export interface ConnectionStatus {
    connected: boolean;
    url: string;
    database: string;
    error: string | null;
}

export interface TableInfo {
    name: string;
    category: string;
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

// View modes for the DevData page
export type ViewMode = 'overview' | 'postgres' | 'qdrant' | 'consistency';

// Data types that can be viewed
export type DataType = 'controls' | 'risks' | 'orgs';

/** Known category display metadata. Unknown categories get auto-generated labels. */
const KNOWN_CATEGORIES: Record<string, { label: string; icon: string }> = {
    reference: { label: 'Reference', icon: 'menu_book' },
    main: { label: 'Main', icon: 'table_chart' },
    relation: { label: 'Relations', icon: 'share' },
    model: { label: 'Models', icon: 'psychology' },
    version: { label: 'Versions', icon: 'history' },
    other: { label: 'Other', icon: 'folder' },
};

/**
 * Get display metadata for a category. Falls back to a readable label
 * derived from the category ID for unknown categories.
 */
export function getCategoryMeta(categoryId: string): { label: string; icon: string } {
    if (KNOWN_CATEGORIES[categoryId]) {
        return KNOWN_CATEGORIES[categoryId];
    }
    // Auto-generate label from ID: "src_controls" -> "Src Controls"
    const label = categoryId
        .split('_')
        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
        .join(' ');
    return { label, icon: 'folder' };
}

/**
 * Group tables by category, preserving server-provided category strings.
 * Returns categories in a stable order (known categories first, then alphabetical).
 */
export function groupTablesByCategory(tables: TableInfo[]): TableCategory[] {
    const groups: Record<string, TableInfo[]> = {};
    for (const table of tables) {
        const cat = table.category || 'other';
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(table);
    }

    // Known categories in display order
    const knownOrder = ['reference', 'main', 'relation', 'model', 'version', 'other'];

    const result: TableCategory[] = [];
    const seen = new Set<string>();

    // Add known categories first (in order)
    for (const catId of knownOrder) {
        if (groups[catId]) {
            result.push({
                id: catId,
                ...getCategoryMeta(catId),
                tables: groups[catId],
            });
            seen.add(catId);
        }
    }

    // Add any remaining categories alphabetically
    for (const catId of Object.keys(groups).sort()) {
        if (!seen.has(catId)) {
            result.push({
                id: catId,
                ...getCategoryMeta(catId),
                tables: groups[catId],
            });
        }
    }

    return result;
}
