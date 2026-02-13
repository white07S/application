import React, { useState, useEffect, useCallback } from 'react';
import PipelinesSidebar from './components/PipelinesSidebar';
import DataTypeSelector from './components/DataTypeSelector';
import UppyUploader from './components/UppyUploader';
import IngestionHistory from './components/IngestionHistory';
import { useAuth } from '../../auth/useAuth';
import { appConfig } from '../../config/appConfig';
import { DataType, IngestionRecord, IngestionHistoryResponse, VALIDATION_RULES } from './types';

const Pipelines: React.FC = () => {
    const { getApiAccessToken } = useAuth();
    const [dataType, setDataType] = useState<DataType>('controls');
    const [history, setHistory] = useState<IngestionRecord[]>([]);
    const [historyLoading, setHistoryLoading] = useState(false);

    // Fetch history
    const fetchHistory = useCallback(async () => {
        setHistoryLoading(true);
        try {
            const token = await getApiAccessToken();
            if (!token) return;

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/pipelines/history?limit=10`, {
                headers: {
                    'X-MS-TOKEN-AAD': token,
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

    const handleUploadComplete = (result: { uploadId: string; filesUploaded: number }) => {
        console.log('Upload complete:', result);
        fetchHistory();
    };

    const handleUploadError = (error: Error) => {
        console.error('Upload error:', error);
    };

    const handleDataTypeChange = (type: DataType) => {
        setDataType(type);
    };

    const rules = VALIDATION_RULES[dataType];

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
                            <h1 className="text-sm font-bold text-text-main flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary text-[18px]">cloud_upload</span>
                                Data Upload
                            </h1>
                            <p className="text-[11px] text-text-sub mt-0.5">
                                Upload risk management data files
                            </p>
                        </div>
                        {/* TUS Badge */}
                        <div className="flex items-center gap-1.5 bg-blue-50 border border-blue-100 rounded px-2 py-1">
                            <span className="material-symbols-outlined text-blue-600 text-[14px]">cloud_sync</span>
                            <span className="text-[10px] font-medium text-blue-700">Resumable Uploads (TUS)</span>
                        </div>
                    </div>

                    {/* Two Column Layout */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        {/* Upload Card - Takes 2 columns */}
                        <div className="lg:col-span-2 bg-white border border-border-light rounded shadow-card">
                            {/* Card Header */}
                            <div className="px-3 py-2 border-b border-border-light bg-surface-light/50 flex items-center justify-between">
                                <h2 className="text-[10px] font-bold text-text-main uppercase tracking-wide flex items-center gap-2">
                                    <span className="material-symbols-outlined text-text-sub text-[14px]">
                                        cloud_sync
                                    </span>
                                    Upload Files
                                </h2>
                            </div>

                            {/* Card Body */}
                            <div className="p-3 space-y-4">
                                {/* Data Type Selector */}
                                <DataTypeSelector
                                    value={dataType}
                                    onChange={handleDataTypeChange}
                                    disabled={false}
                                />

                                {/* TUS/Uppy Upload Zone */}
                                <UppyUploader
                                    dataType={dataType}
                                    rules={rules}
                                    onUploadComplete={handleUploadComplete}
                                    onUploadError={handleUploadError}
                                    disabled={false}
                                />
                            </div>
                        </div>

                        {/* History Section - Takes 1 column */}
                        <div className="lg:col-span-1">
                            <IngestionHistory
                                records={history}
                                isLoading={historyLoading}
                                onRefresh={fetchHistory}
                            />
                        </div>
                    </div>

                    {/* Help Section */}
                    <div className="bg-surface-light border border-border-light rounded p-3">
                        <h3 className="text-[10px] font-bold text-text-main uppercase tracking-wide flex items-center gap-2 mb-2">
                            <span className="material-symbols-outlined text-text-sub text-[14px]">help</span>
                            File Requirements
                        </h3>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
                            <div className="bg-white p-2 rounded border border-border-light">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="material-symbols-outlined text-blue-600 text-[14px]">verified_user</span>
                                    <span className="font-medium text-text-main">Controls</span>
                                    <span className="ml-auto px-1.5 py-0.5 bg-green-100 text-green-700 text-[9px] font-medium rounded">Active</span>
                                </div>
                                <ul className="text-text-sub space-y-0.5 text-[10px]">
                                    <li>1 enterprise-format CSV file</li>
                                    <li>Minimum 5KB</li>
                                </ul>
                            </div>
                            <div className="bg-white p-2 rounded border border-border-light opacity-60">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="material-symbols-outlined text-amber-600 text-[14px]">report_problem</span>
                                    <span className="font-medium text-text-main">Issues</span>
                                    <span className="ml-auto px-1.5 py-0.5 bg-amber-100 text-amber-700 text-[9px] font-medium rounded">In Dev</span>
                                </div>
                                <ul className="text-text-sub space-y-0.5 text-[10px]">
                                    <li>4 CSV files (.csv)</li>
                                    <li>Minimum 5KB each</li>
                                </ul>
                            </div>
                            <div className="bg-white p-2 rounded border border-border-light opacity-60">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="material-symbols-outlined text-green-600 text-[14px]">task_alt</span>
                                    <span className="font-medium text-text-main">Actions</span>
                                    <span className="ml-auto px-1.5 py-0.5 bg-amber-100 text-amber-700 text-[9px] font-medium rounded">In Dev</span>
                                </div>
                                <ul className="text-text-sub space-y-0.5 text-[10px]">
                                    <li>1 CSV file (.csv)</li>
                                    <li>Minimum 5KB</li>
                                </ul>
                            </div>
                        </div>
                        {/* TUS Info Banner */}
                        <div className="mt-2 p-2 bg-blue-50 border border-blue-100 rounded">
                            <div className="flex items-start gap-2">
                                <span className="material-symbols-outlined text-blue-600 text-[14px] mt-0.5">info</span>
                                <div className="text-[10px] text-blue-800">
                                    <p className="font-medium">Resumable Uploads Enabled</p>
                                    <p className="mt-0.5 text-blue-700">
                                        Using the TUS protocol for reliable file uploads. If your connection is interrupted,
                                        the upload will automatically resume from where it left off.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            </div>
        </main>
    );
};

export default Pipelines;
