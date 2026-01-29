import React, { useCallback, useEffect, useRef, useState } from 'react';
import Uppy, { UppyFile, UploadResult } from '@uppy/core';
import Tus from '@uppy/tus';
import { DataType, ValidationRules } from '../types';
import { useAuth } from '../../../auth/useAuth';
import { appConfig } from '../../../config/appConfig';

// Type for our Uppy files with metadata
type FileMeta = {
    data_type: DataType;
    filename?: string;
    batch_session_id?: string;
    expected_files?: string;
};
type UppyFileType = UppyFile<FileMeta, Record<string, unknown>>;

export interface UppyUploaderProps {
    dataType: DataType;
    rules: ValidationRules;
    onUploadComplete?: (result: { uploadId: string; filesUploaded: number }) => void;
    onUploadError?: (error: Error) => void;
    disabled?: boolean;
}

interface FileStatus {
    id: string;
    name: string;
    size: number;
    progress: number;
    status: 'pending' | 'uploading' | 'complete' | 'error';
    error?: string;
}

interface ValidationStatus {
    batch_status?: string;
    validation?: {
        status: string;
        error_details?: {
            isValid: boolean;
            errors: Array<{
                column: string;
                code: string;
                message: string;
                fileName?: string;
            }>;
        };
    };
}

// Generate a unique batch session ID
const generateBatchSessionId = (): string => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        const v = c === 'x' ? r : (r & 0x3) | 0x8;
        return v.toString(16);
    });
};

const UppyUploader: React.FC<UppyUploaderProps> = ({
    dataType,
    rules,
    onUploadComplete,
    onUploadError,
    disabled = false,
}) => {
    const { getApiAccessToken } = useAuth();
    const [isDragging, setIsDragging] = useState(false);
    const [fileStatuses, setFileStatuses] = useState<FileStatus[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadComplete, setUploadComplete] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [validationStatus, setValidationStatus] = useState<ValidationStatus | null>(null);
    const [isValidating, setIsValidating] = useState(false);
    const [validationErrors, setValidationErrors] = useState<string[]>([]);
    const authTokenRef = useRef<string | null>(null);
    const uppyRef = useRef<Uppy<FileMeta, Record<string, unknown>> | null>(null);
    const batchSessionIdRef = useRef<string>(generateBatchSessionId());
    const lastUploadIdRef = useRef<string | null>(null);

    // TUS endpoint
    const tusEndpoint = `${appConfig.api.baseUrl}/api/v2/pipelines/tus/`;

    // Get auth token on mount
    useEffect(() => {
        const fetchToken = async () => {
            try {
                const token = await getApiAccessToken();
                authTokenRef.current = token;
            } catch (err) {
                console.error('Failed to get auth token:', err);
            }
        };
        fetchToken();
    }, [getApiAccessToken]);

    // Poll for validation status after upload completes
    const pollValidationStatus = useCallback(async (tusUploadId: string) => {
        if (!authTokenRef.current) return;

        setIsValidating(true);
        setValidationErrors([]);

        const maxAttempts = 30; // Poll for up to 30 seconds
        let attempts = 0;

        const checkStatus = async (): Promise<void> => {
            try {
                const response = await fetch(
                    `${appConfig.api.baseUrl}/api/v2/pipelines/tus/${tusUploadId}/status`,
                    {
                        headers: {
                            'X-MS-TOKEN-AAD': authTokenRef.current || '',
                        },
                    }
                );

                if (!response.ok) {
                    throw new Error(`Failed to get status: ${response.status}`);
                }

                const data: ValidationStatus & { batch_status?: string; validation?: { status: string; error_details?: unknown } } = await response.json();
                setValidationStatus(data);

                // Check if validation is complete
                if (data.batch_status === 'validated') {
                    setIsValidating(false);
                    setUploadComplete(true);
                    // Auto-close success message after 5 seconds
                    setTimeout(() => setUploadComplete(false), 5000);
                    return;
                }

                if (data.batch_status === 'failed') {
                    setIsValidating(false);
                    // Extract validation errors
                    const errors: string[] = [];
                    if (data.validation?.error_details) {
                        const errorDetails = data.validation.error_details as { errors?: Array<{ column: string; code: string; message: string; fileName?: string }> };
                        if (errorDetails.errors) {
                            errorDetails.errors.slice(0, 5).forEach(err => {
                                errors.push(`${err.column}: ${err.message}${err.fileName ? ` (${err.fileName})` : ''}`);
                            });
                            if (errorDetails.errors.length > 5) {
                                errors.push(`... and ${errorDetails.errors.length - 5} more errors`);
                            }
                        }
                    }
                    if (errors.length === 0) {
                        errors.push('Validation failed. Check server logs for details.');
                    }
                    setValidationErrors(errors);
                    return;
                }

                // Still validating or pending - poll again
                attempts++;
                if (attempts < maxAttempts) {
                    setTimeout(checkStatus, 1000);
                } else {
                    setIsValidating(false);
                    setValidationErrors(['Validation timed out. Please check status later.']);
                }
            } catch (err) {
                console.error('Error polling validation status:', err);
                attempts++;
                if (attempts < maxAttempts) {
                    setTimeout(checkStatus, 1000);
                } else {
                    setIsValidating(false);
                    setValidationErrors(['Failed to check validation status.']);
                }
            }
        };

        checkStatus();
    }, []);

    // Initialize Uppy instance
    useEffect(() => {
        // Generate a new batch session ID for this Uppy instance
        batchSessionIdRef.current = generateBatchSessionId();

        const uppy = new Uppy<FileMeta, Record<string, unknown>>({
            id: `uppy-${dataType}`,
            autoProceed: false,
            allowMultipleUploadBatches: false,
            restrictions: {
                maxNumberOfFiles: rules.fileCount,
                allowedFileTypes: rules.allowedExtensions,
                minFileSize: rules.minSizeKb * 1024,
            },
            meta: {
                data_type: dataType,
                batch_session_id: batchSessionIdRef.current,
                expected_files: String(rules.fileCount),
            },
        });

        // Add TUS plugin
        uppy.use(Tus, {
            endpoint: tusEndpoint,
            retryDelays: [0, 1000, 3000, 5000],
            chunkSize: 5 * 1024 * 1024, // 5MB chunks
            removeFingerprintOnSuccess: true,
            headers: (): Record<string, string> => {
                if (authTokenRef.current) {
                    return { 'X-MS-TOKEN-AAD': authTokenRef.current };
                }
                return {};
            },
        });

        // Event handlers
        uppy.on('file-added', (_file: UppyFileType) => {
            updateFileStatuses(uppy);
        });

        uppy.on('file-removed', (_file: UppyFileType) => {
            updateFileStatuses(uppy);
        });

        uppy.on('upload-progress', (file: UppyFileType | undefined, progress: { bytesUploaded: number; bytesTotal: number }) => {
            if (!file) return;
            const percent = progress.bytesTotal > 0 ? Math.round((progress.bytesUploaded / progress.bytesTotal) * 100) : 0;
            setFileStatuses(prev =>
                prev.map(f =>
                    f.id === file.id
                        ? { ...f, progress: percent, status: 'uploading' }
                        : f
                )
            );
        });

        uppy.on('upload-success', (file: UppyFileType | undefined, _response: Record<string, unknown>) => {
            if (!file) return;
            setFileStatuses(prev =>
                prev.map(f => (f.id === file.id ? { ...f, progress: 100, status: 'complete' } : f))
            );
        });

        uppy.on('upload-error', (file: UppyFileType | undefined, error: Error) => {
            if (!file) return;
            setFileStatuses(prev =>
                prev.map(f => (f.id === file.id ? { ...f, status: 'error', error: error?.message || 'Upload failed' } : f))
            );
        });

        uppy.on('complete', (result: UploadResult<FileMeta, Record<string, unknown>>) => {
            setIsUploading(false);
            const failed = result.failed || [];
            const successful = result.successful || [];
            if (failed.length > 0) {
                setUploadError(`${failed.length} file(s) failed to upload`);
                onUploadError?.(new Error(`${failed.length} file(s) failed to upload`));
            } else if (successful.length > 0) {
                // Get the TUS upload ID from the last successful file
                const lastFile = successful[successful.length - 1];
                const uploadUrl = lastFile.response?.uploadURL;
                const tusUploadId = uploadUrl?.split('/').pop();

                if (tusUploadId) {
                    lastUploadIdRef.current = tusUploadId;
                    // Start polling for validation status
                    pollValidationStatus(tusUploadId);
                } else {
                    setUploadComplete(true);
                    setTimeout(() => setUploadComplete(false), 5000);
                }

                onUploadComplete?.({ uploadId: tusUploadId || 'unknown', filesUploaded: successful.length });
            }
        });

        uppy.on('error', (error: Error) => {
            setIsUploading(false);
            setUploadError(error?.message || 'Upload failed');
            onUploadError?.(error);
        });

        uppyRef.current = uppy;

        return () => {
            uppy.destroy();
        };
    }, [dataType, rules, tusEndpoint, onUploadComplete, onUploadError, pollValidationStatus]);

    // Helper to update file statuses from Uppy state
    const updateFileStatuses = (uppy: Uppy<FileMeta, Record<string, unknown>>) => {
        const files = uppy.getFiles();
        const statuses: FileStatus[] = files.map((file: UppyFileType) => ({
            id: file.id,
            name: file.name || 'Unknown',
            size: file.size || 0,
            progress: file.progress?.percentage || 0,
            status: file.progress?.uploadComplete
                ? 'complete'
                : file.progress?.uploadStarted
                ? 'uploading'
                : 'pending',
            error: undefined,
        }));
        setFileStatuses(statuses);
    };

    // Drag and drop handlers
    const handleDragOver = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            if (!disabled && !isUploading) {
                setIsDragging(true);
            }
        },
        [disabled, isUploading]
    );

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setIsDragging(false);

            if (disabled || isUploading || !uppyRef.current) return;

            const droppedFiles: File[] = Array.from(e.dataTransfer.files);
            droppedFiles.forEach((file: File) => {
                try {
                    uppyRef.current?.addFile({
                        name: file.name,
                        type: file.type,
                        data: file,
                        meta: {
                            data_type: dataType,
                            filename: file.name,
                            batch_session_id: batchSessionIdRef.current,
                            expected_files: String(rules.fileCount),
                        },
                    });
                } catch (err) {
                    const errorMessage = err instanceof Error ? err.message : 'Failed to add file';
                    console.error('Error adding file:', errorMessage);
                    setUploadError(errorMessage);
                }
            });
        },
        [disabled, isUploading, dataType, rules.fileCount]
    );

    // File input handler
    const handleFileSelect = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            if (!uppyRef.current) return;

            const selectedFiles: File[] = Array.from(e.target.files || []);
            selectedFiles.forEach((file: File) => {
                try {
                    uppyRef.current?.addFile({
                        name: file.name,
                        type: file.type,
                        data: file,
                        meta: {
                            data_type: dataType,
                            filename: file.name,
                            batch_session_id: batchSessionIdRef.current,
                            expected_files: String(rules.fileCount),
                        },
                    });
                } catch (err) {
                    const errorMessage = err instanceof Error ? err.message : 'Failed to add file';
                    console.error('Error adding file:', errorMessage);
                    setUploadError(errorMessage);
                }
            });
            e.target.value = '';
        },
        [dataType, rules.fileCount]
    );

    // Remove file handler
    const handleRemoveFile = useCallback((fileId: string) => {
        uppyRef.current?.removeFile(fileId);
    }, []);

    // Start upload
    const handleUpload = useCallback(async () => {
        if (!uppyRef.current) return;

        if (fileStatuses.length !== rules.fileCount) {
            setUploadError(`Please select exactly ${rules.fileCount} file(s)`);
            return;
        }

        // Refresh token before upload
        try {
            const token = await getApiAccessToken();
            authTokenRef.current = token;
        } catch (err) {
            console.error('Failed to refresh token:', err);
        }

        setIsUploading(true);
        setUploadError(null);
        setUploadComplete(false);

        try {
            await uppyRef.current.upload();
        } catch (err) {
            setIsUploading(false);
            const errorMessage = err instanceof Error ? err.message : 'Upload failed';
            setUploadError(errorMessage);
        }
    }, [fileStatuses.length, rules.fileCount, getApiAccessToken]);

    // Clear all files
    const handleClearFiles = useCallback(() => {
        uppyRef.current?.cancelAll();
        setFileStatuses([]);
        setUploadComplete(false);
        setUploadError(null);
        setValidationStatus(null);
        setIsValidating(false);
        setValidationErrors([]);
        // Generate new batch session ID for next upload
        batchSessionIdRef.current = generateBatchSessionId();
    }, []);

    // Format file size
    const formatFileSize = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const remainingFiles = rules.fileCount - fileStatuses.length;
    const canUpload = fileStatuses.length === rules.fileCount && !isUploading && !uploadComplete && !isValidating;

    return (
        <div className="space-y-4">
            {/* Success Message */}
            {uploadComplete && (
                <div className="bg-green-50 border border-green-200 rounded p-3 animate-fade-in">
                    <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-green-600">check_circle</span>
                        <div>
                            <p className="text-xs font-medium text-green-800">Upload & Validation Complete</p>
                            <p className="text-xs text-green-700 mt-1">
                                {fileStatuses.filter(f => f.status === 'complete').length} file(s) uploaded and validated successfully.
                            </p>
                        </div>
                        <button
                            onClick={() => setUploadComplete(false)}
                            className="ml-auto text-green-600 hover:text-green-800"
                        >
                            <span className="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>
                </div>
            )}

            {/* Validating Message */}
            {isValidating && (
                <div className="bg-blue-50 border border-blue-200 rounded p-3 animate-pulse">
                    <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-blue-600 animate-spin">refresh</span>
                        <div>
                            <p className="text-xs font-medium text-blue-800">Validating Files...</p>
                            <p className="text-xs text-blue-600 mt-1">
                                Checking file format and schema. This may take a moment.
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Validation Errors */}
            {validationErrors.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded p-3">
                    <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-red-600">error</span>
                        <div className="flex-1">
                            <p className="text-xs font-medium text-red-800">Validation Failed</p>
                            <ul className="text-xs text-red-600 mt-2 space-y-1">
                                {validationErrors.map((err, idx) => (
                                    <li key={idx} className="flex items-start gap-1">
                                        <span className="text-red-400">•</span>
                                        <span>{err}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <button
                            onClick={() => setValidationErrors([])}
                            className="ml-auto text-red-600 hover:text-red-800"
                        >
                            <span className="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>
                </div>
            )}

            {/* Upload Error Message */}
            {uploadError && (
                <div className="bg-red-50 border border-red-200 rounded p-3">
                    <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-red-600">error</span>
                        <div>
                            <p className="text-xs font-medium text-red-800">Upload Error</p>
                            <p className="text-xs text-red-600 mt-1">{uploadError}</p>
                        </div>
                        <button
                            onClick={() => setUploadError(null)}
                            className="ml-auto text-red-600 hover:text-red-800"
                        >
                            <span className="material-symbols-outlined text-[18px]">close</span>
                        </button>
                    </div>
                </div>
            )}

            {/* Drop Zone */}
            <div
                onClick={() => !disabled && !isUploading && document.getElementById(`file-input-${dataType}`)?.click()}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`relative border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-center transition-all cursor-pointer ${
                    isDragging
                        ? 'border-primary bg-red-50/50'
                        : 'border-border-light hover:border-primary/50 hover:bg-surface-light'
                } ${disabled || isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                style={{
                    backgroundImage: 'radial-gradient(circle, #e5e7eb 1px, transparent 1px)',
                    backgroundSize: '24px 24px',
                }}
            >
                <input
                    id={`file-input-${dataType}`}
                    type="file"
                    accept={rules.allowedExtensions.join(',')}
                    multiple={rules.fileCount > 1}
                    onChange={handleFileSelect}
                    className="hidden"
                    disabled={disabled || isUploading}
                />
                <div
                    className={`h-12 w-12 rounded-full bg-surface-light border border-border-light flex items-center justify-center mb-4 ${
                        isDragging ? 'bg-white text-primary' : 'text-text-sub'
                    }`}
                >
                    <span className="material-symbols-outlined text-[24px]">upload_file</span>
                </div>
                <p className="text-xs font-medium text-text-main">Drag & drop or click to upload</p>
                <p className="text-xs text-text-sub mt-1">
                    {remainingFiles > 0
                        ? `Select ${remainingFiles} more .csv file${remainingFiles > 1 ? 's' : ''} (min ${rules.minSizeKb}KB each)`
                        : 'All required files selected'}
                </p>
                <p className="text-[10px] text-text-sub mt-2 flex items-center gap-1">
                    <span className="material-symbols-outlined text-[12px]">cloud_sync</span>
                    Resumable uploads via TUS protocol
                </p>
            </div>

            {/* File List */}
            {fileStatuses.length > 0 && (
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-text-sub uppercase tracking-wider">
                            Selected Files ({fileStatuses.length}/{rules.fileCount})
                        </span>
                        {!isUploading && (
                            <button
                                onClick={handleClearFiles}
                                className="text-[10px] font-medium text-text-sub hover:text-red-600 flex items-center gap-1 transition-colors"
                            >
                                <span className="material-symbols-outlined text-[14px]">delete</span>
                                Clear All
                            </button>
                        )}
                    </div>
                    <div className="border border-border-light rounded divide-y divide-border-light bg-white max-h-[240px] overflow-y-auto">
                        {fileStatuses.map(file => (
                            <div key={file.id} className="px-4 py-3 hover:bg-surface-light transition-colors">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3 min-w-0 flex-1">
                                        <div
                                            className={`w-8 h-8 rounded flex items-center justify-center ${
                                                file.status === 'complete'
                                                    ? 'bg-green-50 border border-green-100'
                                                    : file.status === 'error'
                                                    ? 'bg-red-50 border border-red-100'
                                                    : file.status === 'uploading'
                                                    ? 'bg-blue-50 border border-blue-100'
                                                    : 'bg-gray-50 border border-gray-100'
                                            }`}
                                        >
                                            <span
                                                className={`material-symbols-outlined text-[16px] ${
                                                    file.status === 'complete'
                                                        ? 'text-green-600'
                                                        : file.status === 'error'
                                                        ? 'text-red-600'
                                                        : file.status === 'uploading'
                                                        ? 'text-blue-600 animate-pulse'
                                                        : 'text-gray-600'
                                                }`}
                                            >
                                                {file.status === 'complete'
                                                    ? 'check_circle'
                                                    : file.status === 'error'
                                                    ? 'error'
                                                    : file.status === 'uploading'
                                                    ? 'cloud_upload'
                                                    : 'description'}
                                            </span>
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className="text-xs font-medium text-text-main truncate" title={file.name}>
                                                {file.name}
                                            </p>
                                            <div className="flex items-center gap-2 text-xs text-text-sub">
                                                <span className="font-mono">{formatFileSize(file.size)}</span>
                                                {file.status === 'uploading' && (
                                                    <>
                                                        <span className="w-1 h-1 rounded-full bg-border-dark"></span>
                                                        <span className="text-blue-600">{file.progress}%</span>
                                                    </>
                                                )}
                                                {file.status === 'complete' && (
                                                    <>
                                                        <span className="w-1 h-1 rounded-full bg-border-dark"></span>
                                                        <span className="text-green-600">Complete</span>
                                                    </>
                                                )}
                                                {file.status === 'error' && file.error && (
                                                    <>
                                                        <span className="w-1 h-1 rounded-full bg-border-dark"></span>
                                                        <span className="text-red-600">{file.error}</span>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    {!isUploading && file.status !== 'complete' && (
                                        <button
                                            type="button"
                                            onClick={() => handleRemoveFile(file.id)}
                                            disabled={disabled}
                                            className="p-1 text-text-sub hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                                        >
                                            <span className="material-symbols-outlined text-[18px]">close</span>
                                        </button>
                                    )}
                                </div>
                                {/* Progress bar */}
                                {file.status === 'uploading' && (
                                    <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-blue-500 transition-all duration-300 ease-out"
                                            style={{ width: `${file.progress}%` }}
                                        />
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Upload Button */}
            <div className="flex items-center justify-between pt-4 border-t border-border-light">
                <div className="text-xs text-text-sub">
                    {fileStatuses.length === 0 ? (
                        <span>Select files to begin upload</span>
                    ) : fileStatuses.length < rules.fileCount ? (
                        <span className="text-amber-600">
                            <span className="material-symbols-outlined text-[14px] align-middle mr-1">warning</span>
                            {rules.fileCount - fileStatuses.length} more file(s) required
                        </span>
                    ) : isValidating ? (
                        <span className="text-blue-600">
                            <span className="material-symbols-outlined text-[14px] align-middle mr-1 animate-spin">refresh</span>
                            Validating files...
                        </span>
                    ) : validationErrors.length > 0 ? (
                        <span className="text-red-600">
                            <span className="material-symbols-outlined text-[14px] align-middle mr-1">error</span>
                            Validation failed - see errors above
                        </span>
                    ) : uploadComplete ? (
                        <span className="text-green-600">
                            <span className="material-symbols-outlined text-[14px] align-middle mr-1">check_circle</span>
                            Files uploaded and validated successfully
                        </span>
                    ) : (
                        <span className="text-green-600">
                            <span className="material-symbols-outlined text-[14px] align-middle mr-1">check_circle</span>
                            Ready to upload
                        </span>
                    )}
                </div>
                <button
                    onClick={handleUpload}
                    disabled={!canUpload || disabled}
                    className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded shadow-sm transition-all ${
                        canUpload && !disabled
                            ? 'bg-primary hover:bg-[#cc0000] text-white'
                            : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                >
                    {isUploading ? (
                        <>
                            <span className="material-symbols-outlined text-[18px] animate-spin">refresh</span>
                            Uploading...
                        </>
                    ) : (
                        <>
                            <span className="material-symbols-outlined text-[18px]">cloud_upload</span>
                            Upload Files
                        </>
                    )}
                </button>
            </div>
        </div>
    );
};

export default UppyUploader;
