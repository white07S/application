import type { FC } from 'react';
import { useState, useEffect, useCallback, useRef } from 'react';
import PipelinesSidebar from './components/PipelinesSidebar';
import { useAuth } from '../../auth/useAuth';
import { appConfig } from '../../config/appConfig';
import { formatDate, formatDuration, getDataTypeColor } from '../../utils/formatters';
import type { ValidatedBatch, JobStatus } from './types';

const ACTIVE_JOBS_KEY = 'pipelines_active_jobs';

const loadActiveJobIds = (): string[] => {
    try {
        const stored = localStorage.getItem(ACTIVE_JOBS_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch {
        return [];
    }
};

const saveActiveJobIds = (jobIds: string[]) => {
    try {
        localStorage.setItem(ACTIVE_JOBS_KEY, JSON.stringify(jobIds));
    } catch {
        // Ignore localStorage errors
    }
};

const MODEL_LABELS: Record<string, string> = {
    taxonomy: 'Taxonomy',
    enrichment: 'Enrichment',
    clean_text: 'Clean Text',
    embeddings: 'Embeddings',
};

const Processing: FC = () => {
    const { getApiAccessToken } = useAuth();
    const [batches, setBatches] = useState<ValidatedBatch[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeJobs, setActiveJobs] = useState<Record<string, JobStatus>>({});
    const [completedJobs, setCompletedJobs] = useState<Record<number, JobStatus>>({});
    const [processingBatches, setProcessingBatches] = useState<Set<number>>(new Set());
    const [resumingJobs, setResumingJobs] = useState(true);
    const pollingRef = useRef<Record<string, NodeJS.Timeout>>({});
    const mountedRef = useRef(true);

    // Fetch validated batches
    const fetchBatches = useCallback(async () => {
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/ingestion/batches`, {
                headers: { 'X-MS-TOKEN-AAD': token },
            });

            if (response.ok) {
                const data = await response.json();
                setBatches(data.batches);
            }
        } catch (err) {
            console.error('Failed to fetch batches:', err);
        } finally {
            setLoading(false);
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

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/ingestion/job/${jobId}`, {
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
                    const storedIds = loadActiveJobIds().filter(id => id !== jobId);
                    saveActiveJobIds(storedIds);
                    setCompletedJobs(prev => ({ ...prev, [job.batch_id]: job }));
                    fetchBatches();
                    return null;
                }
                return job;
            } else if (response.status === 404) {
                const storedIds = loadActiveJobIds().filter(id => id !== jobId);
                saveActiveJobIds(storedIds);
            }
        } catch (err) {
            console.error('Failed to poll job status:', err);
        }
        return null;
    }, [getApiAccessToken, fetchBatches]);

    // Start polling for a job
    const startPolling = useCallback((jobId: string) => {
        if (pollingRef.current[jobId]) {
            clearTimeout(pollingRef.current[jobId]);
        }

        const poll = async () => {
            if (!mountedRef.current) return;
            const job = await pollJobStatus(jobId);
            if (mountedRef.current && job && (job.status === 'pending' || job.status === 'running')) {
                pollingRef.current[jobId] = setTimeout(poll, 500);
            } else {
                delete pollingRef.current[jobId];
            }
        };
        poll();
    }, [pollJobStatus]);

    // Check for running jobs on mount
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

    useEffect(() => {
        mountedRef.current = true;
        checkAndResumeRunningJobs();

        return () => {
            mountedRef.current = false;
            Object.values(pollingRef.current).forEach(timeout => clearTimeout(timeout));
            pollingRef.current = {};
        };
    }, [checkAndResumeRunningJobs]);

    // Start ingestion
    const handleStartIngestion = async (batchId: number) => {
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            setProcessingBatches(prev => new Set(prev).add(batchId));

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/ingestion/insert`, {
                method: 'POST',
                headers: {
                    'X-MS-TOKEN-AAD': token,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ batch_id: batchId }),
            });

            if (response.ok) {
                const data = await response.json();
                const storedIds = loadActiveJobIds();
                if (!storedIds.includes(data.job_id)) {
                    saveActiveJobIds([...storedIds, data.job_id]);
                }
                startPolling(data.job_id);
            } else {
                const error = await response.json();
                alert(`Failed to start ingestion: ${error.detail}`);
                setProcessingBatches(prev => {
                    const next = new Set(prev);
                    next.delete(batchId);
                    return next;
                });
            }
        } catch (err) {
            console.error('Failed to start ingestion:', err);
            setProcessingBatches(prev => {
                const next = new Set(prev);
                next.delete(batchId);
                return next;
            });
        }
    };

    const getCompletedJob = (batchId: number): JobStatus | undefined => completedJobs[batchId];

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
            completed: 'bg-green-100 text-green-700 border-green-200',
            failed: 'bg-red-100 text-red-700 border-red-200',
            running: 'bg-blue-100 text-blue-700 border-blue-200',
            processing: 'bg-blue-100 text-blue-700 border-blue-200',
            pending: 'bg-gray-100 text-gray-700 border-gray-200',
        };
        return (
            <span className={`px-2 py-0.5 text-[10px] font-medium rounded border ${colors[status] || colors.pending}`}>
                {status.toUpperCase()}
            </span>
        );
    };

    const getActiveJob = (batchId: number): JobStatus | undefined => {
        return Object.values(activeJobs).find(
            job => job.batch_id === batchId && (job.status === 'pending' || job.status === 'running')
        );
    };

    // Readiness indicator for a single model
    const ReadinessIcon: FC<{ ready: boolean; label: string }> = ({ ready, label }) => (
        <div className="flex items-center gap-1.5">
            <span className={`material-symbols-outlined text-[14px] ${ready ? 'text-green-600' : 'text-red-400'}`}>
                {ready ? 'check_circle' : 'cancel'}
            </span>
            <span className={`text-[10px] ${ready ? 'text-green-700' : 'text-red-500'}`}>{label}</span>
        </div>
    );

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
                                <span className="material-symbols-outlined text-primary">input</span>
                                Data Ingestion
                            </h1>
                            <p className="text-xs text-text-sub mt-1">
                                Insert validated data into the database
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
                                    {processingBatches.size} ingestion job{processingBatches.size !== 1 ? 's' : ''} in progress
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
                                                            <span>{batch.total_records?.toLocaleString() ?? '—'} records</span>
                                                            <span>•</span>
                                                            <span>{formatDate(batch.created_at)}</span>
                                                            <span>•</span>
                                                            <span>by {batch.uploaded_by || 'Unknown'}</span>
                                                        </div>

                                                        {/* Readiness Indicators */}
                                                        <div className="mt-3 flex items-center gap-4">
                                                            <ReadinessIcon ready={batch.readiness.source_jsonl} label="Source" />
                                                            <ReadinessIcon ready={batch.readiness.taxonomy} label={MODEL_LABELS.taxonomy} />
                                                            <ReadinessIcon ready={batch.readiness.enrichment} label={MODEL_LABELS.enrichment} />
                                                            <ReadinessIcon ready={batch.readiness.clean_text} label={MODEL_LABELS.clean_text} />
                                                            <ReadinessIcon ready={batch.readiness.embeddings} label={MODEL_LABELS.embeddings} />
                                                        </div>

                                                        {/* Not ready message */}
                                                        {!batch.readiness.ready && batch.message && (
                                                            <div className="mt-2 flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                                                                <span className="material-symbols-outlined text-[14px]">warning</span>
                                                                {batch.message}
                                                            </div>
                                                        )}

                                                        {/* Progress Bar (when ingesting) */}
                                                        {activeJob && (activeJob.status === 'running' || activeJob.status === 'pending') && (
                                                            <div className="mt-3">
                                                                <div className="flex items-center justify-between text-xs mb-1">
                                                                    <span className="text-blue-600 font-medium">
                                                                        {activeJob.current_step || (activeJob.status === 'pending' ? 'Starting...' : 'Ingesting...')}
                                                                    </span>
                                                                    <span className="text-text-sub">
                                                                        {activeJob.progress_percent}%
                                                                    </span>
                                                                </div>
                                                                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                                                                    <div
                                                                        className="h-full bg-blue-500 transition-all duration-300"
                                                                        style={{ width: `${activeJob.progress_percent}%` }}
                                                                    />
                                                                </div>
                                                                <div className="flex items-center gap-4 mt-2 text-[10px] text-text-sub">
                                                                    <span>Total: {activeJob.records_total.toLocaleString()}</span>
                                                                    <span>Processed: {activeJob.records_processed.toLocaleString()}</span>
                                                                    <span className="text-green-600">New: {activeJob.records_new.toLocaleString()}</span>
                                                                    <span className="text-amber-600">Changed: {activeJob.records_changed.toLocaleString()}</span>
                                                                    <span className="text-text-main">Unchanged: {activeJob.records_unchanged.toLocaleString()}</span>
                                                                    <span className="text-red-600">Failed: {activeJob.records_failed.toLocaleString()}</span>
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
                                                                            Ingestion {getCompletedJob(batch.batch_id)?.status}
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
                                                                    <div className="mt-2 grid grid-cols-2 sm:grid-cols-5 gap-3">
                                                                        <div className="text-center p-2 bg-white rounded border border-gray-100">
                                                                            <div className="text-lg font-bold text-primary">
                                                                                {getCompletedJob(batch.batch_id)?.records_total.toLocaleString()}
                                                                            </div>
                                                                            <div className="text-[10px] text-text-sub uppercase">Total</div>
                                                                        </div>
                                                                        <div className="text-center p-2 bg-white rounded border border-gray-100">
                                                                            <div className="text-lg font-bold text-green-600">
                                                                                +{getCompletedJob(batch.batch_id)?.records_new.toLocaleString()}
                                                                            </div>
                                                                            <div className="text-[10px] text-text-sub uppercase">New</div>
                                                                        </div>
                                                                        <div className="text-center p-2 bg-white rounded border border-gray-100">
                                                                            <div className="text-lg font-bold text-amber-600">
                                                                                ~{getCompletedJob(batch.batch_id)?.records_changed.toLocaleString()}
                                                                            </div>
                                                                            <div className="text-[10px] text-text-sub uppercase">Changed</div>
                                                                        </div>
                                                                        <div className="text-center p-2 bg-white rounded border border-gray-100">
                                                                            <div className="text-lg font-bold text-text-sub">
                                                                                {getCompletedJob(batch.batch_id)?.records_unchanged.toLocaleString()}
                                                                            </div>
                                                                            <div className="text-[10px] text-text-sub uppercase">Unchanged</div>
                                                                        </div>
                                                                        <div className="text-center p-2 bg-white rounded border border-gray-100">
                                                                            <div className="text-lg font-bold text-text-main">
                                                                                {formatDuration(getCompletedJob(batch.batch_id)?.duration_seconds || 0)}
                                                                            </div>
                                                                            <div className="text-[10px] text-text-sub uppercase">Duration</div>
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

                                                    {/* Action Button */}
                                                    <div className="flex items-center gap-2">
                                                        <button
                                                            onClick={() => handleStartIngestion(batch.batch_id)}
                                                            disabled={!batch.can_ingest || isProcessing}
                                                            className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded transition-colors ${
                                                                batch.can_ingest && !isProcessing
                                                                    ? 'bg-primary hover:bg-primary-dark text-white'
                                                                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                                            }`}
                                                            title={
                                                                !batch.readiness.ready
                                                                    ? 'Model outputs not ready'
                                                                    : !batch.can_ingest
                                                                    ? 'Already ingested'
                                                                    : 'Insert data into database'
                                                            }
                                                        >
                                                            {isProcessing ? (
                                                                <span className="material-symbols-outlined text-[14px] animate-spin">refresh</span>
                                                            ) : (
                                                                <span className="material-symbols-outlined text-[14px]">input</span>
                                                            )}
                                                            {isProcessing ? 'Ingesting...' : 'Insert'}
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
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
                                <p className="font-medium">Data Ingestion</p>
                                <p className="mt-1 text-blue-700">
                                    Click <strong>Insert</strong> to load validated data into the database.
                                    All model outputs (taxonomy, enrichment, clean text, embeddings) must be
                                    available before ingestion can proceed.
                                </p>
                                <p className="mt-2 text-blue-600 text-[10px]">
                                    If model outputs are missing, contact the developer to run the model scripts.
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
