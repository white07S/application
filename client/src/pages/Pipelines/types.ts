export type DataType = 'issues' | 'controls' | 'actions';

export interface ValidationRules {
    fileCount: number;
    minSizeKb: number;
    allowedExtensions: string[];
}

export const VALIDATION_RULES: Record<DataType, ValidationRules> = {
    issues: { fileCount: 4, minSizeKb: 5, allowedExtensions: ['.csv'] },
    controls: { fileCount: 1, minSizeKb: 5, allowedExtensions: ['.csv'] },
    actions: { fileCount: 1, minSizeKb: 5, allowedExtensions: ['.csv'] },
};

export interface SidebarCategory {
    id: string;
    label: string;
    icon: string;
    items: SidebarItem[];
}

export interface SidebarItem {
    id: string;
    label: string;
    icon: string;
    path: string;
    active?: boolean;
}

export interface IngestionRecord {
    ingestionId: string;
    dataType: string;
    filesCount: number;
    fileNames: string[];
    totalSizeBytes: number;
    uploadedBy: string;
    uploadedAt: string;
    status: string;
}

export interface IngestionHistoryResponse {
    records: IngestionRecord[];
    total: number;
}
