/**
 * React hook for managing Qdrant snapshot operations
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../../auth/useAuth';
import {
    qdrantSnapshotApi,
    QdrantSnapshotInfo,
    QdrantSnapshotDetail,
    JobStatusResponse,
    CreateQdrantSnapshotRequest,
    RestoreQdrantSnapshotRequest,
} from '../api/qdrantSnapshotApi';

const POLL_INTERVAL_MS = 2000;
const POLL_MAX_RETRIES = 1800;

interface UseQdrantSnapshotsState {
    snapshots: QdrantSnapshotInfo[];
    total: number;
    page: number;
    pageSize: number;
    hasMore: boolean;

    collections: string[];

    loading: boolean;
    creating: boolean;
    restoring: boolean;
    deleting: boolean;

    currentJob: JobStatusResponse | null;
    jobProgress: number;
    jobStep: string;

    error: string | null;
}

export function useQdrantSnapshots() {
    const { getApiAccessToken } = useAuth();
    const [state, setState] = useState<UseQdrantSnapshotsState>({
        snapshots: [],
        total: 0,
        page: 1,
        pageSize: 20,
        hasMore: false,
        collections: [],
        loading: false,
        creating: false,
        restoring: false,
        deleting: false,
        currentJob: null,
        jobProgress: 0,
        jobStep: '',
        error: null,
    });

    // Fetch available collections
    const fetchCollections = useCallback(async () => {
        try {
            const token = await getApiAccessToken();
            if (!token) return;
            const collections = await qdrantSnapshotApi.listCollections(token);
            setState((prev) => ({ ...prev, collections }));
        } catch {
            // Silently fail — collections list is optional
        }
    }, [getApiAccessToken]);

    // Fetch snapshots
    const fetchSnapshots = useCallback(
        async (page: number = 1, pageSize: number = 20) => {
            setState((prev) => ({ ...prev, loading: true, error: null }));
            try {
                const token = await getApiAccessToken();
                if (!token) throw new Error('No access token available');

                const response = await qdrantSnapshotApi.listSnapshots(token, page, pageSize);
                setState((prev) => ({
                    ...prev,
                    snapshots: response.snapshots,
                    total: response.total,
                    page: response.page,
                    pageSize: response.page_size,
                    hasMore: response.has_more,
                    loading: false,
                }));
            } catch (err: any) {
                setState((prev) => ({
                    ...prev,
                    error: err.message || 'Failed to fetch Qdrant snapshots',
                    loading: false,
                }));
            }
        },
        [getApiAccessToken]
    );

    const beginJobPolling = useCallback(
        (token: string, jobId: string, operation: 'creating' | 'restoring') => {
            void (async () => {
                try {
                    const finalStatus = await qdrantSnapshotApi.pollJobStatus(
                        token,
                        jobId,
                        (status) => {
                            setState((prev) => ({
                                ...prev,
                                currentJob: status,
                                jobProgress: status.progress_percent,
                                jobStep: status.current_step || prev.jobStep || 'Processing...',
                            }));
                        },
                        POLL_MAX_RETRIES,
                        POLL_INTERVAL_MS
                    );

                    await fetchSnapshots(state.page, state.pageSize);

                    setState((prev) => ({
                        ...prev,
                        creating: operation === 'creating' ? false : prev.creating,
                        restoring: operation === 'restoring' ? false : prev.restoring,
                        currentJob: null,
                        jobProgress: 0,
                        jobStep: '',
                        error:
                            finalStatus.status === 'failed'
                                ? finalStatus.error_message ||
                                  (operation === 'creating'
                                      ? 'Qdrant snapshot creation failed'
                                      : 'Qdrant snapshot restore failed')
                                : prev.error,
                    }));
                } catch (err: any) {
                    setState((prev) => ({
                        ...prev,
                        creating: operation === 'creating' ? false : prev.creating,
                        restoring: operation === 'restoring' ? false : prev.restoring,
                        currentJob: null,
                        jobProgress: 0,
                        jobStep: '',
                        error: err.message || 'Failed while tracking Qdrant snapshot job',
                    }));
                }
            })();
        },
        [fetchSnapshots, state.page, state.pageSize]
    );

    // Create snapshot
    const createSnapshot = useCallback(
        async (request: CreateQdrantSnapshotRequest) => {
            setState((prev) => ({
                ...prev,
                creating: true,
                error: null,
                currentJob: null,
                jobProgress: 0,
                jobStep: 'Initializing...',
            }));

            try {
                const token = await getApiAccessToken();
                if (!token) throw new Error('No access token available');

                const resp = await qdrantSnapshotApi.createSnapshot(token, request);
                if (!resp.success) throw new Error(resp.message);

                setState((prev) => ({
                    ...prev,
                    currentJob: {
                        job_id: resp.job_id,
                        status: 'pending',
                        progress_percent: 0,
                        current_step: 'Snapshot creation queued',
                        started_at: new Date().toISOString(),
                    },
                    jobStep: 'Snapshot creation queued. You can continue using other views.',
                }));

                beginJobPolling(token, resp.job_id, 'creating');
                return resp.snapshot_id;
            } catch (err: any) {
                setState((prev) => ({
                    ...prev,
                    creating: false,
                    error: err.message || 'Failed to create Qdrant snapshot',
                    currentJob: null,
                }));
                return null;
            }
        },
        [beginJobPolling, getApiAccessToken]
    );

    // Restore snapshot
    const restoreSnapshot = useCallback(
        async (snapshotId: string, request: RestoreQdrantSnapshotRequest) => {
            setState((prev) => ({
                ...prev,
                restoring: true,
                error: null,
                currentJob: null,
                jobProgress: 0,
                jobStep: 'Initializing restore...',
            }));

            try {
                const token = await getApiAccessToken();
                if (!token) throw new Error('No access token available');

                const resp = await qdrantSnapshotApi.restoreSnapshot(token, snapshotId, request);
                if (!resp.success) throw new Error(resp.message);

                setState((prev) => ({
                    ...prev,
                    currentJob: {
                        job_id: resp.job_id,
                        status: 'pending',
                        progress_percent: 0,
                        current_step: 'Snapshot restore queued',
                        started_at: new Date().toISOString(),
                    },
                    jobStep: 'Snapshot restore queued. You can continue using other views.',
                }));

                beginJobPolling(token, resp.job_id, 'restoring');
                return true;
            } catch (err: any) {
                setState((prev) => ({
                    ...prev,
                    restoring: false,
                    error: err.message || 'Failed to restore Qdrant snapshot',
                    currentJob: null,
                }));
                return false;
            }
        },
        [beginJobPolling, getApiAccessToken]
    );

    // Delete snapshot
    const deleteSnapshot = useCallback(
        async (snapshotId: string) => {
            setState((prev) => ({ ...prev, deleting: true, error: null }));
            try {
                const token = await getApiAccessToken();
                if (!token) throw new Error('No access token available');

                const resp = await qdrantSnapshotApi.deleteSnapshot(token, snapshotId);
                if (!resp.success) throw new Error(resp.message);

                await fetchSnapshots(state.page, state.pageSize);
                setState((prev) => ({ ...prev, deleting: false }));
                return true;
            } catch (err: any) {
                setState((prev) => ({
                    ...prev,
                    deleting: false,
                    error: err.message || 'Failed to delete Qdrant snapshot',
                }));
                return false;
            }
        },
        [getApiAccessToken, fetchSnapshots, state.page, state.pageSize]
    );

    const changePage = useCallback(
        (newPage: number) => {
            fetchSnapshots(newPage, state.pageSize);
        },
        [fetchSnapshots, state.pageSize]
    );

    // Initial load
    useEffect(() => {
        fetchSnapshots();
        fetchCollections();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    return {
        ...state,
        fetchSnapshots,
        fetchCollections,
        createSnapshot,
        restoreSnapshot,
        deleteSnapshot,
        changePage,
        formatFileSize: qdrantSnapshotApi.formatFileSize,
        formatDate: qdrantSnapshotApi.formatDate,
    };
}
