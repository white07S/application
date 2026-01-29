import React, { useState, useEffect, useCallback, useRef } from 'react';
import PipelinesSidebar from './components/PipelinesSidebar';
import { useAuth } from '../../auth/useAuth';
import { appConfig } from '../../config/appConfig';
import { formatBytes, formatDuration, getDataTypeColor } from '../../utils/formatters';

interface ParquetFile {
    filename: string;
    path: string;
    size_bytes: number;
    modified_at: number;
}

interface ValidatedBatch {
    batch_id: number;
    upload_id: string;
    data_type: string;
    status: string;
    file_count: number | null;
    total_records: number | null;
    pk_records: number | null;
    uploaded_by: string | null;
    created_at: string;
    parquet_files: ParquetFile[];
    parquet_count: number;
    ingestion_status: string | null;
    ingestion_run_id: number | null;
    model_run_status: string | null;
    model_run_id: number | null;
    can_ingest: boolean;
    can_run_model: boolean;
}

interface JobStatus {
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
    records_updated: number;
    records_skipped: number;
    records_failed: number;
    started_at: string | null;
    completed_at: string | null;
    error_message: string | null;
    steps: Array<JobStep>;
    // Summary fields
    data_type: string;
    duration_seconds: number;
    db_total_records: number;
    pk_records?: number | null;
    // Batch tracking
    batches_total: number;
    batches_completed: number;
}

interface JobStep {
    step: number;
    name: string;
    target_table?: string;
    type?: string;
    pipeline_run_id?: number;
    records_processed: number;
    records_new?: number;
    records_updated?: number;
    records_skipped?: number;
    records_failed?: number;
    error?: string;
    reason?: string;
    completed_at: string;
}

interface PipelineStatus {
    batch_id: number;
    upload_id: string;
    data_type: string;
    ingestion?: {
        status: string;
        records_total: number;
        records_processed: number;
        records_inserted: number;
        records_updated: number;
        records_skipped: number;
        records_failed: number;
        pipeline_run_id: number;
    } | null;
    steps: Array<{
        name: string;
        type: string;
        status: string;
        records_processed: number;
        records_failed: number;
        records_skipped: number;
        pipeline_run_id?: number;
        records_total?: number;
    }>;
    records_total?: number;
    records_processed?: number;
    records_failed?: number;
}

const ACTIVE_JOBS_KEY = 'pipelines_active_jobs';

// Helper to load active jobs from localStorage
const loadActiveJobIds = (): string[] => {
    try {
        const stored = localStorage.getItem(ACTIVE_JOBS_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch {
        return [];
    }
};

// Helper to save active jobs to localStorage
const saveActiveJobIds = (jobIds: string[]) => {
    try {
        localStorage.setItem(ACTIVE_JOBS_KEY, JSON.stringify(jobIds));
    } catch {
        // Ignore localStorage errors
    }
};

const Processing: React.FC = () => {
    const { getApiAccessToken } = useAuth();
    const [batches, setBatches] = useState<ValidatedBatch[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeJobs, setActiveJobs] = useState<Record<string, JobStatus>>({});
    const [completedJobs, setCompletedJobs] = useState<Record<number, JobStatus>>({});
    const [processingBatches, setProcessingBatches] = useState<Set<number>>(new Set());
    const [expandedBatch, setExpandedBatch] = useState<number | null>(null);
    const [batchStatuses, setBatchStatuses] = useState<Record<number, PipelineStatus>>({});
    const [resumingJobs, setResumingJobs] = useState(true);
    const pollingRef = useRef<Record<string, NodeJS.Timeout>>({});
    const mountedRef = useRef(true);

    // Fetch validated batches
    const fetchBatches = useCallback(async () => {
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/processing/batches`, {
                headers: { 'X-MS-TOKEN-AAD': token },
            });

            if (response.ok) {
                const data = await response.json();
                setBatches(data.batches);
                // Fetch pipeline statuses for each batch asynchronously
                data.batches.forEach((b: ValidatedBatch) => fetchBatchStatus(b.batch_id));
            }
        } catch (err) {
            console.error('Failed to fetch batches:', err);
        } finally {
            setLoading(false);
        }
    }, [getApiAccessToken]);

    const fetchBatchStatus = useCallback(async (batchId: number) => {
        try {
            const token = await getApiAccessToken();
            if (!token) return;
            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/processing/batch/${batchId}/status`, {
                headers: { 'X-MS-TOKEN-AAD': token },
            });
            if (response.ok) {
                const status: PipelineStatus = await response.json();
                setBatchStatuses(prev => ({ ...prev, [batchId]: status }));
            }
        } catch (err) {
            console.error('Failed to fetch batch status', err);
        }
    }, [getApiAccessToken]);

    useEffect(() => {
        fetchBatches();
    }, [fetchBatches]);

    // Poll job status
    const pollJobStatus = useCallback(async (jobId: string): Promise<JobStatus | null> => {
        if (!mountedRef.current) return null;

        try {
            const token = await getApiAccessToken();
            if (!token) return null;

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/processing/job/${jobId}`, {
                headers: { 'X-MS-TOKEN-AAD': token },
            });

            if (response.ok) {
                const job: JobStatus = await response.json();
                if (!mountedRef.current) return null;

                setActiveJobs(prev => ({ ...prev, [jobId]: job }));

                if (job.status === 'completed' || job.status === 'failed') {
                    setProcessingBatches(prev => {
                        const next = new Set(prev);
                        next.delete(job.batch_id);
                        return next;
                    });
                    // Remove from localStorage
                    const storedIds = loadActiveJobIds().filter(id => id !== jobId);
                    saveActiveJobIds(storedIds);
                    // Store completed job for summary display
                    setCompletedJobs(prev => ({ ...prev, [job.batch_id]: job }));
                    // Refresh batches to get updated status
                    fetchBatches();
                    fetchBatchStatus(job.batch_id);
                    return null; // Stop polling
                }
                return job;
            } else if (response.status === 404) {
                // Job no longer exists, remove from localStorage
                const storedIds = loadActiveJobIds().filter(id => id !== jobId);
                saveActiveJobIds(storedIds);
            }
        } catch (err) {
            console.error('Failed to poll job status:', err);
        }
        return null;
    }, [getApiAccessToken, fetchBatches, fetchBatchStatus]);

    // Start polling for a job
    const startPolling = useCallback((jobId: string) => {
        // Clear existing polling for this job if any
        if (pollingRef.current[jobId]) {
            clearTimeout(pollingRef.current[jobId]);
        }

        const poll = async () => {
            if (!mountedRef.current) return;

            const job = await pollJobStatus(jobId);
            if (mountedRef.current && job && (job.status === 'pending' || job.status === 'running')) {
                pollingRef.current[jobId] = setTimeout(poll, 500);
            } else {
                // Clean up polling reference
                delete pollingRef.current[jobId];
            }
        };
        poll();
    }, [pollJobStatus]);

    // Check for running jobs on mount and resume polling
    const checkAndResumeRunningJobs = useCallback(async () => {
        const storedJobIds = loadActiveJobIds();
        if (storedJobIds.length === 0) {
            setResumingJobs(false);
            return;
        }

        for (const jobId of storedJobIds) {
            const job = await pollJobStatus(jobId);
            if (job && (job.status === 'pending' || job.status === 'running')) {
                setProcessingBatches(prev => new Set(prev).add(job.batch_id));
                startPolling(jobId);
            }
        }
        setResumingJobs(false);
    }, [pollJobStatus, startPolling]);

    // On mount, check for running jobs
    useEffect(() => {
        mountedRef.current = true;
        checkAndResumeRunningJobs();

        return () => {
            mountedRef.current = false;
            // Clean up all polling
            Object.values(pollingRef.current).forEach(timeout => clearTimeout(timeout));
            pollingRef.current = {};
        };
    }, [checkAndResumeRunningJobs]);

    // Start processing (full pipeline: ingestion + models)
    const handleStartProcessing = async (batchId: number) => {
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            setProcessingBatches(prev => new Set(prev).add(batchId));

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/processing/ingest`, {
                method: 'POST',
                headers: {
                    'X-MS-TOKEN-AAD': token,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ batch_id: batchId }),
            });

            if (response.ok) {
                const data = await response.json();
                // Save job ID to localStorage for persistence
                const storedIds = loadActiveJobIds();
                if (!storedIds.includes(data.job_id)) {
                    saveActiveJobIds([...storedIds, data.job_id]);
                }
                startPolling(data.job_id);
            } else {
                const error = await response.json();
                alert(`Failed to start processing: ${error.detail}`);
                setProcessingBatches(prev => {
                    const next = new Set(prev);
                    next.delete(batchId);
                    return next;
                });
            }
        } catch (err) {
            console.error('Failed to start processing:', err);
            setProcessingBatches(prev => {
                const next = new Set(prev);
                next.delete(batchId);
                return next;
            });
        }
    };

    const formatDate = (isoString: string): string => {
        return new Date(isoString).toLocaleString();
    };

    // Get completed job for a batch (for showing summary)
    const getCompletedJob = (batchId: number): JobStatus | undefined => {
        return completedJobs[batchId];
    };

    // Dismiss completed job summary
    const dismissCompletedJob = (batchId: number) => {
        setCompletedJobs(prev => {
            const next = { ...prev };
            delete next[batchId];
            return next;
        });
    };

    const getStatusBadge = (status: string | null) => {
        if (!status) return null;
        const colors: Record<string, string> = {
            success: 'bg-green-100 text-green-700 border-green-200',
            failed: 'bg-red-100 text-red-700 border-red-200',
            running: 'bg-blue-100 text-blue-700 border-blue-200',
            pending: 'bg-gray-100 text-gray-700 border-gray-200',
        };
        return (
            <span className={`px-2 py-0.5 text-[10px] font-medium rounded border ${colors[status] || colors.pending}`}>
                {status.toUpperCase()}
            </span>
        );
    };

    // Get active job for a batch
    const getActiveJob = (batchId: number): JobStatus | undefined => {
        return Object.values(activeJobs).find(
            job => job.batch_id === batchId && (job.status === 'pending' || job.status === 'running')
        );
    };

    const getDisplayedSteps = (batchId: number): JobStatus['steps'] | undefined => {
        const active = getActiveJob(batchId);
        if (active && active.steps?.length) return active.steps;
        const completed = getCompletedJob(batchId);
        if (completed?.steps?.length) return completed.steps;
        const status = batchStatuses[batchId];
        if (status?.steps?.length) {
            return status.steps.map((s, idx) => ({
                step: idx + 1,
                name: s.name,
                type: s.type,
                pipeline_run_id: s.pipeline_run_id,
                records_processed: s.records_processed,
                records_skipped: s.records_skipped,
                records_failed: s.records_failed,
                completed_at: '',
            }));
        }
        return undefined;
    };

    return (
        <main className="min-h-screen">
            <div className="w-full max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4">
                <div className="flex">
                    {/* Sidebar */}
                    <div className="sticky top-12 h-[calc(100vh-48px)] overflow-y-auto py-4">
                        <PipelinesSidebar />
                    </div>

                    {/* Main Content */}
                    <div className="flex-1 min-w-0 py-4 pl-4 flex flex-col gap-4">
                    {/* Page Header */}
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-xl font-bold text-text-main flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary">manufacturing</span>
                                Data Processing
                            </h1>
                            <p className="text-xs text-text-sub mt-1">
                                Run the complete pipeline on validated data
                            </p>
                        </div>
                        <button
                            onClick={fetchBatches}
                            disabled={loading}
                            className="flex items-center gap-2 px-4 py-2 text-xs font-medium border border-border-light rounded hover:bg-surface-light transition-colors disabled:opacity-50"
                        >
                            <span className={`material-symbols-outlined text-[16px] ${loading ? 'animate-spin' : ''}`}>
                                refresh
                            </span>
                            Refresh
                        </button>
                    </div>

                    {/* Active Jobs Banner */}
                    {processingBatches.size > 0 && (
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-blue-600 animate-spin">progress_activity</span>
                            <div className="flex-1">
                                <p className="text-sm font-medium text-blue-800">
                                    {processingBatches.size} job{processingBatches.size !== 1 ? 's' : ''} in progress
                                </p>
                                <p className="text-xs text-blue-600">
                                    Progress is tracked even if you navigate away from this page
                                </p>
                            </div>
                        </div>
                    )}

                    {/* Batches List */}
                    <div className="bg-white border border-border-light rounded shadow-card">
                        <div className="px-5 py-3 border-b border-border-light bg-surface-light/50">
                            <h2 className="text-xs font-bold text-text-main uppercase tracking-wide flex items-center gap-2">
                                <span className="material-symbols-outlined text-text-sub text-[16px]">inventory_2</span>
                                Validated Batches ({batches.length})
                            </h2>
                        </div>

                        {loading || resumingJobs ? (
                            <div className="p-8 text-center">
                                <span className="material-symbols-outlined animate-spin text-2xl text-text-sub">refresh</span>
                                <p className="text-xs text-text-sub mt-2">
                                    {resumingJobs ? 'Checking for running jobs...' : 'Loading batches...'}
                                </p>
                            </div>
                        ) : batches.length === 0 ? (
                            <div className="p-8 text-center">
                                <span className="material-symbols-outlined text-3xl text-border-dark">inbox</span>
                                <p className="text-xs text-text-sub mt-2">No validated batches available</p>
                            </div>
                        ) : (
                            <div className="divide-y divide-border-light">
                                {batches.map(batch => {
                                    const activeJob = getActiveJob(batch.batch_id);
                                    const isProcessing = processingBatches.has(batch.batch_id);
                                    const isExpanded = expandedBatch === batch.batch_id;

                                    return (
                                        <div key={batch.batch_id} className="hover:bg-surface-light/50 transition-colors">
                                            {/* Batch Row */}
                                            <div className="px-5 py-4">
                                                <div className="flex items-start justify-between gap-4">
                                                    {/* Batch Info */}
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-3 mb-2">
                                                            <span className="font-mono text-sm font-bold text-primary">
                                                                {batch.upload_id}
                                                            </span>
                                                            <span className={`px-2 py-0.5 text-[10px] font-medium rounded border uppercase ${getDataTypeColor(batch.data_type)}`}>
                                                                {batch.data_type}
                                                            </span>
                                                            {getStatusBadge(batch.ingestion_status)}
                                                        </div>
                                                        <div className="flex items-center gap-4 text-xs text-text-sub">
                                                            <span>{batch.parquet_count} parquet files</span>
                                                            <span>•</span>
                                                            <span>{batch.pk_records ?? batch.total_records ?? '—'} records (by PK)</span>
                                                            <span>•</span>
                                                            <span>{formatDate(batch.created_at)}</span>
                                                            <span>•</span>
                                                            <span>by {batch.uploaded_by}</span>
                                                        </div>

                                                        {/* Progress Bar (when processing) */}
                                                        {activeJob && (activeJob.status === 'running' || activeJob.status === 'pending') && (
                                                            <div className="mt-3">
                                                                <div className="flex items-center justify-between text-xs mb-1">
                                                                    <span className="text-blue-600 font-medium">
                                                                        {activeJob.current_step || (activeJob.status === 'pending' ? 'Starting...' : 'Processing...')}
                                                                    </span>
                                                                    <span className="text-text-sub">
                                                                        {activeJob.progress_percent}%
                                                                        {activeJob.batches_total > 0 && (
                                                                            <span className="ml-2 text-primary font-medium">
                                                                                (Batch {activeJob.batches_completed + 1}/{activeJob.batches_total})
                                                                            </span>
                                                                        )}
                                                                    </span>
                                                                </div>
                                                                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                                                    <div
                                                                        className="h-full bg-blue-500 transition-all duration-300"
                                                                        style={{ width: `${activeJob.progress_percent}%` }}
                                                                    />
                                                                </div>
                                                                <div className="flex items-center gap-4 mt-2 text-[10px] text-text-sub">
                                                                    <span>Total: {activeJob.records_total}</span>
                                                                    <span>Processed: {activeJob.records_processed}</span>
                                                                    <span className="text-red-600">Failed: {activeJob.records_failed}</span>
                                                                    <span className="text-green-600">New: {activeJob.records_new}</span>
                                                                    <span className="text-amber-600">Updated: {activeJob.records_updated}</span>
                                                                </div>
                                                            </div>
                                                        )}

                                                        {/* Completion Summary */}
                                                        {getCompletedJob(batch.batch_id) && (
                                                            <div className={`mt-3 p-3 rounded-lg border ${
                                                                getCompletedJob(batch.batch_id)?.status === 'completed'
                                                                    ? 'bg-green-50 border-green-200'
                                                                    : 'bg-red-50 border-red-200'
                                                            }`}>
                                                                <div className="flex items-start justify-between">
                                                                    <div className="flex items-center gap-2">
                                                                        <span className={`material-symbols-outlined text-[18px] ${
                                                                            getCompletedJob(batch.batch_id)?.status === 'completed'
                                                                                ? 'text-green-600'
                                                                                : 'text-red-600'
                                                                        }`}>
                                                                            {getCompletedJob(batch.batch_id)?.status === 'completed' ? 'check_circle' : 'error'}
                                                                        </span>
                                                                        <span className={`text-xs font-bold uppercase ${
                                                                            getCompletedJob(batch.batch_id)?.status === 'completed'
                                                                                ? 'text-green-700'
                                                                                : 'text-red-700'
                                                                        }`}>
                                                                            Pipeline {getCompletedJob(batch.batch_id)?.status}
                                                                        </span>
                                                                    </div>
                                                                    <button
                                                                        onClick={() => dismissCompletedJob(batch.batch_id)}
                                                                        className="text-gray-400 hover:text-gray-600"
                                                                    >
                                                                        <span className="material-symbols-outlined text-[16px]">close</span>
                                                                    </button>
                                                                </div>

                                                                {getCompletedJob(batch.batch_id)?.status === 'completed' && (
                                                                    <div className="mt-2 grid grid-cols-2 sm:grid-cols-2 md:grid-cols-4 xl:grid-cols-4 gap-3">
                                                                        <div className="text-center p-2 bg-white rounded border border-gray-100">
                                                                            <div className="text-lg font-bold text-primary">
                                                                                {getCompletedJob(batch.batch_id)?.db_total_records.toLocaleString()}
                                                                            </div>
                                                                            <div className="text-[10px] text-text-sub uppercase">
                                                                                Total in DB
                                                                            </div>
                                                                        </div>
                                                                        <div className="text-center p-2 bg-white rounded border border-gray-100">
                                                                            <div className="text-lg font-bold text-green-600">
                                                                                +{getCompletedJob(batch.batch_id)?.records_new.toLocaleString()}
                                                                            </div>
                                                                            <div className="text-[10px] text-text-sub uppercase">
                                                                                New Records
                                                                            </div>
                                                                        </div>
                                                                        <div className="text-center p-2 bg-white rounded border border-gray-100">
                                                                            <div className="text-lg font-bold text-amber-600">
                                                                                ~{getCompletedJob(batch.batch_id)?.records_updated.toLocaleString()}
                                                                            </div>
                                                                            <div className="text-[10px] text-text-sub uppercase">
                                                                                Updated
                                                                            </div>
                                                                        </div>
                                                                        <div className="text-center p-2 bg-white rounded border border-gray-100">
                                                                            <div className="text-lg font-bold text-text-main">
                                                                                {formatDuration(getCompletedJob(batch.batch_id)?.duration_seconds || 0)}
                                                                            </div>
                                                                            <div className="text-[10px] text-text-sub uppercase">
                                                                                Duration
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                )}

                                                                {getCompletedJob(batch.batch_id)?.status === 'failed' && (
                                                                    <div className="mt-2 text-xs text-red-700">
                                                                        {getCompletedJob(batch.batch_id)?.error_message}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>

                                                    {/* Action Buttons */}
                                                    <div className="flex items-center gap-2">
                                                        {/* Expand/Collapse Button */}
                                                        <button
                                                            onClick={() => {
                                                                const next = isExpanded ? null : batch.batch_id;
                                                                setExpandedBatch(next);
                                                                if (next) {
                                                                    fetchBatchStatus(next);
                                                                }
                                                            }}
                                                            className="p-2 text-text-sub hover:text-primary hover:bg-surface-light rounded transition-colors"
                                                            title="View details"
                                                        >
                                                            <span className="material-symbols-outlined text-[18px]">
                                                                {isExpanded ? 'expand_less' : 'expand_more'}
                                                            </span>
                                                        </button>

                                                        {/* Process Button */}
                                                        <button
                                                            onClick={() => handleStartProcessing(batch.batch_id)}
                                                            disabled={!batch.can_ingest || isProcessing}
                                                            className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded transition-colors ${
                                                                batch.can_ingest && !isProcessing
                                                                    ? 'bg-primary hover:bg-primary-dark text-white'
                                                                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                                            }`}
                                                            title={!batch.can_ingest ? 'Already processed' : 'Run full pipeline (ingest + models)'}
                                                        >
                                                            {isProcessing ? (
                                                                <span className="material-symbols-outlined text-[14px] animate-spin">refresh</span>
                                                            ) : (
                                                                <span className="material-symbols-outlined text-[14px]">play_arrow</span>
                                                            )}
                                                            {isProcessing ? 'Processing...' : 'Process'}
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Expanded Details */}
                                            {isExpanded && (
                                                    <div className="px-5 pb-4 border-t border-border-light bg-surface-light/30">
                                                        <div className="pt-4">
                                                            <h4 className="text-[10px] font-bold text-text-sub uppercase tracking-wider mb-2">
                                                                Parquet Files
                                                            </h4>
                                                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3">
                                                            {batch.parquet_files.map(file => (
                                                                <div
                                                                    key={file.filename}
                                                                    className="flex items-center gap-2 px-3 py-2 bg-white border border-border-light rounded text-xs"
                                                                >
                                                                    <span className="material-symbols-outlined text-[14px] text-text-sub">description</span>
                                                                    <span className="font-mono text-text-main truncate">{file.filename}</span>
                                                                    <span className="text-text-sub ml-auto">{formatBytes(file.size_bytes)}</span>
                                                                </div>
                                                            ))}
                                                        </div>

                                                        {/* Pipeline status snapshot */}
                                                        {batchStatuses[batch.batch_id] && (
                                                            <div className="mt-4">
                                                                <h4 className="text-[10px] font-bold text-text-sub uppercase tracking-wider mb-2">
                                                                    Pipeline Status
                                                                </h4>
                                                                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                                                                    <div className="bg-white border border-border-light rounded p-2 text-xs">
                                                                        <div className="flex items-center justify-between">
                                                                            <span className="font-semibold">Ingestion</span>
                                                                            {getStatusBadge(batch.ingestion_status)}
                                                                        </div>
                                                                        {batchStatuses[batch.batch_id]?.ingestion && (
                                                                            <div className="mt-1 text-text-sub space-y-1">
                                                                                <div>Processed: {batchStatuses[batch.batch_id]?.ingestion?.records_processed}</div>
                                                                                <div className="text-green-600">Inserted: {batchStatuses[batch.batch_id]?.ingestion?.records_inserted}</div>
                                                                                <div className="text-amber-600">Updated: {batchStatuses[batch.batch_id]?.ingestion?.records_updated}</div>
                                                                                {batchStatuses[batch.batch_id]?.ingestion && batchStatuses[batch.batch_id]!.ingestion!.records_failed > 0 && (
                                                                                    <div className="text-red-600">Failed: {batchStatuses[batch.batch_id]?.ingestion?.records_failed}</div>
                                                                                )}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                    {batchStatuses[batch.batch_id]?.steps.map(step => (
                                                                        <div key={step.type} className="bg-white border border-border-light rounded p-2 text-xs">
                                                                            <div className="flex items-center justify-between">
                                                                                <span className="font-semibold">{step.name}</span>
                                                                                {getStatusBadge(step.status)}
                                                                            </div>
                                                                            <div className="mt-1 text-text-sub space-y-1">
                                                                                <div>Processed: {step.records_processed}</div>
                                                                                {step.records_skipped > 0 && <div className="text-amber-600">Skipped: {step.records_skipped}</div>}
                                                                                {step.records_failed > 0 && <div className="text-red-600">Failed: {step.records_failed}</div>}
                                                                            </div>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}

                                                        {/* Job Steps (if completed) */}
                                                        {getDisplayedSteps(batch.batch_id) && getDisplayedSteps(batch.batch_id)!.length > 0 && (
                                                            <div className="mt-4">
                                                                <h4 className="text-[10px] font-bold text-text-sub uppercase tracking-wider mb-2">
                                                                    Processing Steps
                                                                </h4>
                                                                <div className="space-y-1">
                                                                    {getDisplayedSteps(batch.batch_id)!.map(step => (
                                                                        <div
                                                                            key={step.step}
                                                                            className={`flex items-center gap-3 px-3 py-2 bg-white border border-border-light rounded text-xs ${
                                                                                step.error ? 'border-red-200 bg-red-50/50' : ''
                                                                            }`}
                                                                        >
                                                                            <span className={`material-symbols-outlined text-[14px] ${
                                                                                step.error ? 'text-red-600' : 'text-green-600'
                                                                            }`}>
                                                                                {step.error ? 'error' : 'check_circle'}
                                                                            </span>
                                                                            <span className="font-medium">{step.name}</span>
                                                                            {step.target_table && (
                                                                                <span className="text-text-sub">→ {step.target_table}</span>
                                                                            )}
                                                                            {step.type && (
                                                                                <span className="text-text-sub uppercase text-[10px] bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">
                                                                                    {step.type}
                                                                                </span>
                                                                            )}
                                                                            <span className="ml-auto text-text-sub">
                                                                                {step.records_processed} records
                                                                                {step.records_new !== undefined && (
                                                                                    <span className="text-green-600 ml-2">+{step.records_new} new</span>
                                                                                )}
                                                                                {step.records_updated !== undefined && (
                                                                                    <span className="text-amber-600 ml-2">~{step.records_updated} updated</span>
                                                                                )}
                                                                                {step.records_failed !== undefined && step.records_failed > 0 && (
                                                                                    <span className="text-red-600 ml-2">failed {step.records_failed}</span>
                                                                                )}
                                                                            </span>
                                                                            {step.error && (
                                                                                <span className="text-xs text-red-600 ml-2 truncate max-w-xs" title={step.error}>
                                                                                    {step.error}
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {/* Info Banner */}
                    <div className="bg-blue-50 border border-blue-100 rounded p-3">
                        <div className="flex items-start gap-2">
                            <span className="material-symbols-outlined text-blue-600">info</span>
                            <div className="text-xs text-blue-800">
                                <p className="font-medium">End-to-End Processing Pipeline</p>
                                <p className="mt-1 text-blue-700">
                                    Click <strong>Process</strong> to run the complete pipeline on validated data:
                                </p>
                                <ul className="mt-2 text-blue-700 space-y-1 ml-4 list-disc">
                                    <li><strong>Ingestion</strong> - Loads data into tables with delta detection (new vs updated records)</li>
                                    <li><strong>NFR Taxonomy</strong> - Classifies records using ML model</li>
                                    <li><strong>Enrichment</strong> - Adds additional context and metadata</li>
                                    <li><strong>Embeddings</strong> - Generates vector embeddings for semantic search</li>
                                </ul>
                                <p className="mt-2 text-blue-600 text-[10px]">
                                    Processing runs in batches with automatic retries. Failed records are logged to a failure file.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            </div>
        </main>
    );
};

export default Processing;
