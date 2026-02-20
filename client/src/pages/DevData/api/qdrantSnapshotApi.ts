/**
 * API client for Qdrant snapshot operations
 */

import { appConfig } from '../../../config/appConfig';

export interface CreateQdrantSnapshotRequest {
    name: string;
    description?: string;
    collection_name: string;
}

export interface CreateQdrantSnapshotResponse {
    success: boolean;
    message: string;
    job_id: string;
    snapshot_id: string;
}

export interface RestoreQdrantSnapshotRequest {
    force?: boolean;
}

export interface RestoreQdrantSnapshotResponse {
    success: boolean;
    message: string;
    job_id: string;
}

export interface QdrantSnapshotInfo {
    id: string;
    name: string;
    description?: string;
    collection_name: string;
    file_size: number;
    points_count: number;
    created_by: string;
    created_at: string;
    status: string;
    restored_count: number;
}

export interface QdrantSnapshotDetail extends QdrantSnapshotInfo {
    qdrant_snapshot_name?: string;
    file_path: string;
    checksum?: string;
    vectors_count: number;
    last_restored_at?: string;
    last_restored_by?: string;
    error_message?: string;
}

export interface QdrantSnapshotListResponse {
    snapshots: QdrantSnapshotInfo[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
}

export interface DeleteQdrantSnapshotResponse {
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
}

class QdrantSnapshotApi {
    private baseUrl: string;

    constructor() {
        this.baseUrl = `${appConfig.api.baseUrl}/api/v2/devdata/qdrant-snapshots`;
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
        request: CreateQdrantSnapshotRequest
    ): Promise<CreateQdrantSnapshotResponse> {
        return this.request<CreateQdrantSnapshotResponse>(
            '/create',
            { method: 'POST', body: JSON.stringify(request) },
            token
        );
    }

    async listSnapshots(
        token: string,
        page: number = 1,
        pageSize: number = 20,
        collectionName?: string
    ): Promise<QdrantSnapshotListResponse> {
        const params = new URLSearchParams({
            page: page.toString(),
            page_size: pageSize.toString(),
        });

        if (collectionName) {
            params.append('collection_name', collectionName);
        }

        return this.request<QdrantSnapshotListResponse>(
            `/list?${params}`,
            { method: 'GET' },
            token
        );
    }

    async getSnapshot(token: string, snapshotId: string): Promise<QdrantSnapshotDetail> {
        return this.request<QdrantSnapshotDetail>(
            `/${encodeURIComponent(snapshotId)}`,
            { method: 'GET' },
            token
        );
    }

    async restoreSnapshot(
        token: string,
        snapshotId: string,
        request: RestoreQdrantSnapshotRequest
    ): Promise<RestoreQdrantSnapshotResponse> {
        return this.request<RestoreQdrantSnapshotResponse>(
            `/${encodeURIComponent(snapshotId)}/restore`,
            { method: 'POST', body: JSON.stringify(request) },
            token
        );
    }

    async deleteSnapshot(
        token: string,
        snapshotId: string
    ): Promise<DeleteQdrantSnapshotResponse> {
        return this.request<DeleteQdrantSnapshotResponse>(
            `/${encodeURIComponent(snapshotId)}`,
            { method: 'DELETE' },
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

    async listCollections(token: string): Promise<string[]> {
        const resp = await this.request<{ collections: string[] }>(
            '/collections',
            { method: 'GET' },
            token
        );
        return resp.collections;
    }

    async pollJobStatus(
        token: string,
        jobId: string,
        onProgress?: (status: JobStatusResponse) => void,
        maxRetries: number = 1800,
        interval: number = 2000
    ): Promise<JobStatusResponse> {
        let retries = 0;

        while (retries < maxRetries) {
            const status = await this.getJobStatus(token, jobId);
            if (onProgress) onProgress(status);
            if (status.status === 'completed' || status.status === 'failed') return status;
            await new Promise((resolve) => setTimeout(resolve, interval));
            retries++;
        }

        throw new Error('Job polling timed out');
    }

    formatFileSize(bytes: number): string {
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        if (bytes === 0) return '0 Bytes';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i];
    }

    formatDate(dateString: string): string {
        return new Date(dateString).toLocaleString();
    }
}

export const qdrantSnapshotApi = new QdrantSnapshotApi();
