/**
 * API client for PostgreSQL snapshot operations
 */

import { appConfig } from '../../../config/appConfig';

// Types for API responses
export interface CreateSnapshotRequest {
    name: string;
    description?: string;
}

export interface CreateSnapshotResponse {
    success: boolean;
    message: string;
    job_id: string;
    snapshot_id: string;
}

export interface RestoreSnapshotRequest {
    create_pre_restore_backup: boolean;
    force?: boolean;
}

export interface RestoreSnapshotResponse {
    success: boolean;
    message: string;
    job_id: string;
    pre_restore_snapshot_id?: string;
}

export interface SnapshotInfo {
    id: string;
    name: string;
    description?: string;
    file_size: number;
    created_by: string;
    created_at: string;
    status: string;
    is_scheduled: boolean;
    restored_count: number;
}

export interface SnapshotDetail extends SnapshotInfo {
    file_path: string;
    checksum?: string;
    alembic_version: string;
    table_count: number;
    total_records: number;
    last_restored_at?: string;
    last_restored_by?: string;
    schedule_id?: string;
    error_message?: string;
}

export interface SnapshotListResponse {
    snapshots: SnapshotInfo[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
}

export interface CompareSnapshotsRequest {
    snapshot_id_1: string;
    snapshot_id_2: string;
    include_schema?: boolean;
    include_data?: boolean;
}

export interface SnapshotComparison {
    snapshot_1: SnapshotInfo;
    snapshot_2: SnapshotInfo;
    size_diff: number;
    record_diff: number;
    table_diff: number;
    alembic_version_match: boolean;
    created_time_diff_hours: number;
    schema_changes?: string[];
    data_changes?: Record<string, any>;
}

export interface DeleteSnapshotResponse {
    success: boolean;
    message: string;
    deleted_file: boolean;
}

export interface JobStatusResponse {
    job_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress_percent: number;
    current_step: string;
    started_at: string;
    completed_at?: string;
    error_message?: string;
    result?: Record<string, any>;
}

export interface ToolsVerifyResponse {
    tools_available: boolean;
    details: string;
    backup_path: string;
    backup_path_exists: boolean;
}

class SnapshotApi {
    private baseUrl: string;

    constructor() {
        this.baseUrl = `${appConfig.api.baseUrl}/api/v2/devdata/snapshots`;
    }

    private async request<T>(
        endpoint: string,
        options: RequestInit,
        token: string
    ): Promise<T> {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                'X-MS-TOKEN-AAD': token,
                ...options.headers,
            },
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || `Request failed: ${response.status}`);
        }

        return response.json();
    }

    async createSnapshot(
        token: string,
        request: CreateSnapshotRequest
    ): Promise<CreateSnapshotResponse> {
        return this.request<CreateSnapshotResponse>(
            '/create',
            {
                method: 'POST',
                body: JSON.stringify(request),
            },
            token
        );
    }

    async listSnapshots(
        token: string,
        page: number = 1,
        pageSize: number = 20,
        filterScheduled?: boolean
    ): Promise<SnapshotListResponse> {
        const params = new URLSearchParams({
            page: page.toString(),
            page_size: pageSize.toString(),
        });

        if (filterScheduled !== undefined) {
            params.append('filter_scheduled', filterScheduled.toString());
        }

        return this.request<SnapshotListResponse>(
            `/list?${params}`,
            { method: 'GET' },
            token
        );
    }

    async getSnapshot(token: string, snapshotId: string): Promise<SnapshotDetail> {
        return this.request<SnapshotDetail>(
            `/${encodeURIComponent(snapshotId)}`,
            { method: 'GET' },
            token
        );
    }

    async restoreSnapshot(
        token: string,
        snapshotId: string,
        request: RestoreSnapshotRequest
    ): Promise<RestoreSnapshotResponse> {
        return this.request<RestoreSnapshotResponse>(
            `/${encodeURIComponent(snapshotId)}/restore`,
            {
                method: 'POST',
                body: JSON.stringify(request),
            },
            token
        );
    }

    async deleteSnapshot(
        token: string,
        snapshotId: string
    ): Promise<DeleteSnapshotResponse> {
        return this.request<DeleteSnapshotResponse>(
            `/${encodeURIComponent(snapshotId)}`,
            { method: 'DELETE' },
            token
        );
    }

    async compareSnapshots(
        token: string,
        request: CompareSnapshotsRequest
    ): Promise<SnapshotComparison> {
        return this.request<SnapshotComparison>(
            '/compare',
            {
                method: 'POST',
                body: JSON.stringify(request),
            },
            token
        );
    }

    async getJobStatus(token: string, jobId: string): Promise<JobStatusResponse> {
        return this.request<JobStatusResponse>(
            `/job/${encodeURIComponent(jobId)}/status`,
            { method: 'GET' },
            token
        );
    }

    async verifyTools(token: string): Promise<ToolsVerifyResponse> {
        return this.request<ToolsVerifyResponse>(
            '/tools/verify',
            { method: 'GET' },
            token
        );
    }

    /**
     * Poll job status until completion or failure
     */
    async pollJobStatus(
        token: string,
        jobId: string,
        onProgress?: (status: JobStatusResponse) => void,
        maxRetries: number = 1800, // 60 minutes with 2-second intervals
        interval: number = 2000
    ): Promise<JobStatusResponse> {
        let retries = 0;

        while (retries < maxRetries) {
            const status = await this.getJobStatus(token, jobId);

            if (onProgress) {
                onProgress(status);
            }

            if (status.status === 'completed' || status.status === 'failed') {
                return status;
            }

            await new Promise((resolve) => setTimeout(resolve, interval));
            retries++;
        }

        throw new Error('Job polling timed out');
    }

    /**
     * Format file size for display
     */
    formatFileSize(bytes: number): string {
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        if (bytes === 0) return '0 Bytes';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }

    /**
     * Format date for display
     */
    formatDate(dateString: string): string {
        return new Date(dateString).toLocaleString();
    }
}

export const snapshotApi = new SnapshotApi();
