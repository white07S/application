/**
 * React hook for managing PostgreSQL snapshot operations
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../../auth/useAuth';
import {
    snapshotApi,
    SnapshotInfo,
    SnapshotDetail,
    JobStatusResponse,
    CreateSnapshotRequest,
    RestoreSnapshotRequest,
} from '../api/snapshotApi';

const SNAPSHOT_JOB_POLL_INTERVAL_MS = 2000;
const SNAPSHOT_JOB_POLL_MAX_RETRIES = 1800;

interface UseSnapshotsState {
    // Snapshot list
    snapshots: SnapshotInfo[];
    total: number;
    page: number;
    pageSize: number;
    hasMore: boolean;

    // Loading states
    loading: boolean;
    creating: boolean;
    restoring: boolean;
    deleting: boolean;

    // Job tracking
    currentJob: JobStatusResponse | null;
    jobProgress: number;
    jobStep: string;

    // Errors
    error: string | null;

    // Tools verification
    toolsAvailable: boolean | null;
    toolsMessage: string | null;
}

export function useSnapshots() {
    const { getApiAccessToken } = useAuth();
    const [state, setState] = useState<UseSnapshotsState>({
        snapshots: [],
        total: 0,
        page: 1,
        pageSize: 20,
        hasMore: false,
        loading: false,
        creating: false,
        restoring: false,
        deleting: false,
        currentJob: null,
        jobProgress: 0,
        jobStep: '',
        error: null,
        toolsAvailable: null,
        toolsMessage: null,
    });

    // Verify backup tools are available
    const verifyTools = useCallback(async () => {
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const result = await snapshotApi.verifyTools(token);
            setState((prev) => ({
                ...prev,
                toolsAvailable: result.tools_available,
                toolsMessage: result.details,
            }));
        } catch (err: any) {
            setState((prev) => ({
                ...prev,
                toolsAvailable: false,
                toolsMessage: err.message,
            }));
        }
    }, [getApiAccessToken]);

    // Fetch snapshots list
    const fetchSnapshots = useCallback(
        async (page: number = 1, pageSize: number = 20) => {
            setState((prev) => ({ ...prev, loading: true, error: null }));

            try {
                const token = await getApiAccessToken();
                if (!token) {
                    throw new Error('No access token available');
                }

                const response = await snapshotApi.listSnapshots(token, page, pageSize);

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
                    error: err.message || 'Failed to fetch snapshots',
                    loading: false,
                }));
            }
        },
        [getApiAccessToken]
    );

    const beginJobPolling = useCallback(
        (
            token: string,
            jobId: string,
            operation: 'creating' | 'restoring'
        ) => {
            void (async () => {
                try {
                    const finalStatus = await snapshotApi.pollJobStatus(
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
                        SNAPSHOT_JOB_POLL_MAX_RETRIES,
                        SNAPSHOT_JOB_POLL_INTERVAL_MS
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
                                      ? 'Snapshot creation failed'
                                      : 'Snapshot restore failed')
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
                        error:
                            err.message ||
                            (operation === 'creating'
                                ? 'Failed while tracking snapshot creation'
                                : 'Failed while tracking snapshot restore'),
                    }));
                }
            })();
        },
        [fetchSnapshots, state.page, state.pageSize]
    );

    // Get snapshot details
    const getSnapshotDetail = useCallback(
        async (snapshotId: string): Promise<SnapshotDetail | null> => {
            try {
                const token = await getApiAccessToken();
                if (!token) return null;

                return await snapshotApi.getSnapshot(token, snapshotId);
            } catch (err: any) {
                setState((prev) => ({
                    ...prev,
                    error: err.message || 'Failed to get snapshot details',
                }));
                return null;
            }
        },
        [getApiAccessToken]
    );

    // Create a new snapshot
    const createSnapshot = useCallback(
        async (request: CreateSnapshotRequest) => {
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
                if (!token) {
                    throw new Error('No access token available');
                }

                // Start snapshot creation
                const createResponse = await snapshotApi.createSnapshot(token, request);

                if (!createResponse.success) {
                    throw new Error(createResponse.message);
                }

                setState((prev) => ({
                    ...prev,
                    currentJob: {
                        job_id: createResponse.job_id,
                        status: 'pending',
                        progress_percent: 0,
                        current_step: 'Snapshot creation queued',
                        started_at: new Date().toISOString(),
                    },
                    jobStep: 'Snapshot creation queued. You can continue using other views.',
                }));

                beginJobPolling(token, createResponse.job_id, 'creating');

                return createResponse.snapshot_id;
            } catch (err: any) {
                setState((prev) => ({
                    ...prev,
                    creating: false,
                    error: err.message || 'Failed to create snapshot',
                    currentJob: null,
                }));
                return null;
            }
        },
        [beginJobPolling, getApiAccessToken]
    );

    // Restore from a snapshot
    const restoreSnapshot = useCallback(
        async (snapshotId: string, request: RestoreSnapshotRequest) => {
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
                if (!token) {
                    throw new Error('No access token available');
                }

                // Start restore
                const restoreResponse = await snapshotApi.restoreSnapshot(
                    token,
                    snapshotId,
                    request
                );

                if (!restoreResponse.success) {
                    throw new Error(restoreResponse.message);
                }

                setState((prev) => ({
                    ...prev,
                    currentJob: {
                        job_id: restoreResponse.job_id,
                        status: 'pending',
                        progress_percent: 0,
                        current_step: 'Snapshot restore queued',
                        started_at: new Date().toISOString(),
                    },
                    jobStep: 'Snapshot restore queued. You can continue using other views.',
                }));

                beginJobPolling(token, restoreResponse.job_id, 'restoring');

                return true;
            } catch (err: any) {
                setState((prev) => ({
                    ...prev,
                    restoring: false,
                    error: err.message || 'Failed to restore snapshot',
                    currentJob: null,
                }));
                return false;
            }
        },
        [beginJobPolling, getApiAccessToken]
    );

    // Delete a snapshot
    const deleteSnapshot = useCallback(
        async (snapshotId: string) => {
            setState((prev) => ({ ...prev, deleting: true, error: null }));

            try {
                const token = await getApiAccessToken();
                if (!token) {
                    throw new Error('No access token available');
                }

                const response = await snapshotApi.deleteSnapshot(token, snapshotId);

                if (!response.success) {
                    throw new Error(response.message);
                }

                // Refresh snapshot list
                await fetchSnapshots(state.page, state.pageSize);

                setState((prev) => ({ ...prev, deleting: false }));
                return true;
            } catch (err: any) {
                setState((prev) => ({
                    ...prev,
                    deleting: false,
                    error: err.message || 'Failed to delete snapshot',
                }));
                return false;
            }
        },
        [getApiAccessToken, fetchSnapshots, state.page, state.pageSize]
    );

    // Compare two snapshots
    const compareSnapshots = useCallback(
        async (snapshotId1: string, snapshotId2: string) => {
            try {
                const token = await getApiAccessToken();
                if (!token) return null;

                return await snapshotApi.compareSnapshots(token, {
                    snapshot_id_1: snapshotId1,
                    snapshot_id_2: snapshotId2,
                    include_schema: true,
                    include_data: true,
                });
            } catch (err: any) {
                setState((prev) => ({
                    ...prev,
                    error: err.message || 'Failed to compare snapshots',
                }));
                return null;
            }
        },
        [getApiAccessToken]
    );

    // Check job status
    const checkJobStatus = useCallback(
        async (jobId: string): Promise<JobStatusResponse | null> => {
            try {
                const token = await getApiAccessToken();
                if (!token) return null;

                return await snapshotApi.getJobStatus(token, jobId);
            } catch (err: any) {
                return null;
            }
        },
        [getApiAccessToken]
    );

    // Change page
    const changePage = useCallback(
        (newPage: number) => {
            fetchSnapshots(newPage, state.pageSize);
        },
        [fetchSnapshots, state.pageSize]
    );

    // Initial load
    useEffect(() => {
        fetchSnapshots();
        verifyTools();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    return {
        // State
        ...state,

        // Actions
        fetchSnapshots,
        getSnapshotDetail,
        createSnapshot,
        restoreSnapshot,
        deleteSnapshot,
        compareSnapshots,
        checkJobStatus,
        changePage,
        verifyTools,

        // Utilities
        formatFileSize: snapshotApi.formatFileSize,
        formatDate: snapshotApi.formatDate,
    };
}
