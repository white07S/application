export type DataType = 'issues' | 'controls' | 'actions';

export interface FileValidation {
    file: File;
    isValid: boolean;
    error?: string;
}

export interface ValidationRules {
    fileCount: number;
    minSizeKb: number;
    allowedExtensions: string[];
}

export const VALIDATION_RULES: Record<DataType, ValidationRules> = {
    issues: { fileCount: 4, minSizeKb: 5, allowedExtensions: ['.xlsx'] },
    controls: { fileCount: 1, minSizeKb: 5, allowedExtensions: ['.xlsx'] },
    actions: { fileCount: 1, minSizeKb: 5, allowedExtensions: ['.xlsx'] },
};

export interface IngestResponse {
    success: boolean;
    ingestionId: string;
    message: string;
    filesUploaded: number;
    dataType: string;
}

export interface UploadState {
    files: File[];
    validations: FileValidation[];
    isUploading: boolean;
    error: string | null;
    success: IngestResponse | null;
}

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
