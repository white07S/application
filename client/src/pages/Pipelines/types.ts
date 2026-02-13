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

export interface ReadinessInfo {
    ready: boolean;
    source_jsonl: boolean;
    taxonomy: boolean;
    enrichment: boolean;
    clean_text: boolean;
    embeddings: boolean;
    missing_models: string[];
    missing_control_ids: Record<string, string[]>;
    message: string | null;
}

export interface ValidatedBatch {
    batch_id: number;
    upload_id: string;
    data_type: string;
    status: string;
    file_count: number | null;
    total_records: number | null;
    uploaded_by: string | null;
    created_at: string;
    readiness: ReadinessInfo;
    can_ingest: boolean;
    ingestion_status: string | null;
    message: string | null;
}

export interface JobStatus {
    job_id: string;
    job_type: string;
    batch_id: number;
    upload_id: string;
    status: string;
    progress_percent: number;
    current_step: string;
    records_total: number;
    records_processed: number;
    records_new: number;
    records_changed: number;
    records_unchanged: number;
    records_failed: number;
    started_at: string | null;
    completed_at: string | null;
    created_at: string | null;
    error_message: string | null;
    duration_seconds: number;
}
