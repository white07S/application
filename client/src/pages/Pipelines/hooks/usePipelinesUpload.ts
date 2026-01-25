import { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { appConfig } from '../../../config/appConfig';
import {
    DataType,
    FileValidation,
    UploadState,
    IngestResponse,
    IngestionRecord,
    IngestionHistoryResponse,
    VALIDATION_RULES,
} from '../types';

const initialState: UploadState = {
    files: [],
    validations: [],
    isUploading: false,
    error: null,
    success: null,
};

export const usePipelinesUpload = () => {
    const { getApiAccessToken } = useAuth();
    const [state, setState] = useState<UploadState>(initialState);
    const [dataType, setDataType] = useState<DataType>('issues');
    const [history, setHistory] = useState<IngestionRecord[]>([]);
    const [historyLoading, setHistoryLoading] = useState(false);

    const fetchHistory = useCallback(async () => {
        setHistoryLoading(true);
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const response = await fetch(`${appConfig.api.baseUrl}/api/pipelines/history?limit=10`, {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });

            if (response.ok) {
                const data: IngestionHistoryResponse = await response.json();
                setHistory(data.records);
            }
        } catch (err) {
            console.error('Failed to fetch history:', err);
        } finally {
            setHistoryLoading(false);
        }
    }, [getApiAccessToken]);

    useEffect(() => {
        fetchHistory();
    }, [fetchHistory]);

    const validateFile = useCallback((file: File, rules: typeof VALIDATION_RULES['issues']): FileValidation => {
        const extension = '.' + file.name.split('.').pop()?.toLowerCase();

        if (!rules.allowedExtensions.includes(extension)) {
            return {
                file,
                isValid: false,
                error: `Invalid file type. Only ${rules.allowedExtensions.join(', ')} files are allowed.`,
            };
        }

        const fileSizeKb = file.size / 1024;
        if (fileSizeKb < rules.minSizeKb) {
            return {
                file,
                isValid: false,
                error: `File is too small (${fileSizeKb.toFixed(1)}KB). Minimum size is ${rules.minSizeKb}KB.`,
            };
        }

        return { file, isValid: true };
    }, []);

    const validateAllFiles = useCallback((files: File[], type: DataType): { isValid: boolean; validations: FileValidation[]; error: string | null } => {
        const rules = VALIDATION_RULES[type];

        // Check file count
        if (files.length !== rules.fileCount) {
            return {
                isValid: false,
                validations: files.map(f => ({ file: f, isValid: false })),
                error: `Expected ${rules.fileCount} file(s) for ${type}, got ${files.length}.`,
            };
        }

        // Validate each file
        const validations = files.map(file => validateFile(file, rules));
        const allValid = validations.every(v => v.isValid);

        return {
            isValid: allValid,
            validations,
            error: allValid ? null : validations.find(v => !v.isValid)?.error || 'Validation failed',
        };
    }, [validateFile]);

    const addFiles = useCallback((newFiles: File[]) => {
        setState(prev => {
            const allFiles = [...prev.files, ...newFiles];
            const { validations, error } = validateAllFiles(allFiles, dataType);
            return {
                ...prev,
                files: allFiles,
                validations,
                error,
                success: null,
            };
        });
    }, [dataType, validateAllFiles]);

    const removeFile = useCallback((index: number) => {
        setState(prev => {
            const newFiles = prev.files.filter((_, i) => i !== index);
            const { validations, error } = validateAllFiles(newFiles, dataType);
            return {
                ...prev,
                files: newFiles,
                validations,
                error: newFiles.length === 0 ? null : error,
                success: null,
            };
        });
    }, [dataType, validateAllFiles]);

    const clearFiles = useCallback(() => {
        setState(initialState);
    }, []);

    const changeDataType = useCallback((type: DataType) => {
        setDataType(type);
        setState(prev => {
            if (prev.files.length === 0) {
                return { ...prev, error: null, success: null };
            }
            const { validations, error } = validateAllFiles(prev.files, type);
            return {
                ...prev,
                validations,
                error,
                success: null,
            };
        });
    }, [validateAllFiles]);

    const upload = useCallback(async () => {
        const rules = VALIDATION_RULES[dataType];

        // Final validation before upload
        if (state.files.length !== rules.fileCount) {
            setState(prev => ({
                ...prev,
                error: `Please select exactly ${rules.fileCount} file(s) for ${dataType}.`,
            }));
            return;
        }

        const { isValid, error } = validateAllFiles(state.files, dataType);
        if (!isValid) {
            setState(prev => ({ ...prev, error }));
            return;
        }

        setState(prev => ({ ...prev, isUploading: true, error: null }));

        try {
            const token = await getApiAccessToken();
            if (!token) {
                throw new Error('Failed to acquire access token');
            }

            const formData = new FormData();
            formData.append('data_type', dataType);
            state.files.forEach(file => {
                formData.append('files', file);
            });

            const response = await fetch(`${appConfig.api.baseUrl}/api/pipelines/ingest`, {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${token}`,
                },
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Upload failed');
            }

            const data: IngestResponse = await response.json();

            setState({
                files: [],
                validations: [],
                isUploading: false,
                error: null,
                success: data,
            });

            // Refresh history after successful upload
            fetchHistory();
        } catch (err: any) {
            setState(prev => ({
                ...prev,
                isUploading: false,
                error: err.message || 'Upload failed',
            }));
        }
    }, [state.files, dataType, getApiAccessToken, validateAllFiles]);

    return {
        ...state,
        dataType,
        addFiles,
        removeFile,
        clearFiles,
        changeDataType,
        upload,
        rules: VALIDATION_RULES[dataType],
        history,
        historyLoading,
        refreshHistory: fetchHistory,
    };
};
