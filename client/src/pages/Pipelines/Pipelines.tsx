import React from 'react';
import PipelinesSidebar from './components/PipelinesSidebar';
import DataTypeSelector from './components/DataTypeSelector';
import FileUploadZone from './components/FileUploadZone';
import IngestionHistory from './components/IngestionHistory';
import { usePipelinesUpload } from './hooks/usePipelinesUpload';

const Pipelines: React.FC = () => {
    const {
        files,
        validations,
        isUploading,
        error,
        success,
        dataType,
        rules,
        addFiles,
        removeFile,
        clearFiles,
        changeDataType,
        upload,
        history,
        historyLoading,
        refreshHistory,
    } = usePipelinesUpload();

    const canUpload = files.length === rules.fileCount && validations.every(v => v.isValid);

    return (
        <main className="min-h-screen">
            <div className="flex">
                {/* Sidebar */}
                <div className="sticky top-12 h-[calc(100vh-48px)] overflow-y-auto py-6 pl-6">
                    <PipelinesSidebar />
                </div>

                {/* Main Content */}
                <div className="flex-1 min-w-0 p-6 flex flex-col gap-6">
                        {/* Page Header */}
                        <div className="flex items-center justify-between">
                            <div>
                                <h1 className="text-xl font-bold text-text-main flex items-center gap-2">
                                    <span className="material-symbols-outlined text-primary">cloud_upload</span>
                                    Data Ingestion
                                </h1>
                                <p className="text-xs text-text-sub mt-1">
                                    Upload risk management data files for processing
                                </p>
                            </div>
                        </div>

                        {/* Success Message */}
                        {success && (
                            <div className="bg-green-50 border border-green-200 rounded p-4">
                                <div className="flex items-start gap-3">
                                    <span className="material-symbols-outlined text-green-600">check_circle</span>
                                    <div>
                                        <p className="text-sm font-medium text-green-800">
                                            Upload Successful
                                        </p>
                                        <p className="text-xs text-green-700 mt-1">
                                            Ingestion ID: <span className="font-mono font-medium">{success.ingestionId}</span>
                                        </p>
                                        <p className="text-xs text-green-600 mt-0.5">
                                            {success.filesUploaded} file(s) uploaded for {success.dataType}
                                        </p>
                                    </div>
                                    <button
                                        onClick={clearFiles}
                                        className="ml-auto text-green-600 hover:text-green-800"
                                    >
                                        <span className="material-symbols-outlined text-[18px]">close</span>
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Error Message */}
                        {error && (
                            <div className="bg-red-50 border border-red-200 rounded p-4">
                                <div className="flex items-start gap-3">
                                    <span className="material-symbols-outlined text-red-600">error</span>
                                    <div>
                                        <p className="text-sm font-medium text-red-800">
                                            Upload Error
                                        </p>
                                        <p className="text-xs text-red-600 mt-1">{error}</p>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Two Column Layout */}
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            {/* Upload Card - Takes 2 columns */}
                            <div className="lg:col-span-2 bg-white border border-border-light rounded shadow-card">
                                {/* Card Header */}
                                <div className="px-5 py-3 border-b border-border-light bg-surface-light/50 flex items-center justify-between">
                                    <h2 className="text-xs font-bold text-text-main uppercase tracking-wide flex items-center gap-2">
                                        <span className="material-symbols-outlined text-text-sub text-[16px]">upload_file</span>
                                        Upload Files
                                    </h2>
                                    {files.length > 0 && (
                                        <button
                                            onClick={clearFiles}
                                            disabled={isUploading}
                                            className="text-[10px] font-medium text-text-sub hover:text-red-600 flex items-center gap-1 transition-colors"
                                        >
                                            <span className="material-symbols-outlined text-[14px]">delete</span>
                                            Clear All
                                        </button>
                                    )}
                                </div>

                                {/* Card Body */}
                                <div className="p-5 space-y-6">
                                    {/* Data Type Selector */}
                                    <DataTypeSelector
                                        value={dataType}
                                        onChange={changeDataType}
                                        disabled={isUploading}
                                    />

                                    {/* File Upload Zone */}
                                    <FileUploadZone
                                        files={files}
                                        validations={validations}
                                        rules={rules}
                                        onFilesAdded={addFiles}
                                        onFileRemoved={removeFile}
                                        disabled={isUploading}
                                    />

                                    {/* Upload Button */}
                                    <div className="flex items-center justify-between pt-4 border-t border-border-light">
                                        <div className="text-xs text-text-sub">
                                            {files.length === 0 ? (
                                                <span>Select files to begin upload</span>
                                            ) : files.length < rules.fileCount ? (
                                                <span className="text-amber-600">
                                                    <span className="material-symbols-outlined text-[14px] align-middle mr-1">warning</span>
                                                    {rules.fileCount - files.length} more file(s) required
                                                </span>
                                            ) : !validations.every(v => v.isValid) ? (
                                                <span className="text-red-600">
                                                    <span className="material-symbols-outlined text-[14px] align-middle mr-1">error</span>
                                                    Some files have validation errors
                                                </span>
                                            ) : (
                                                <span className="text-green-600">
                                                    <span className="material-symbols-outlined text-[14px] align-middle mr-1">check_circle</span>
                                                    Ready to upload
                                                </span>
                                            )}
                                        </div>
                                        <button
                                            onClick={upload}
                                            disabled={!canUpload || isUploading}
                                            className={`flex items-center gap-2 px-5 py-2.5 text-xs font-semibold rounded shadow-sm transition-all ${
                                                canUpload && !isUploading
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
                            </div>

                            {/* History Section - Takes 1 column */}
                            <div className="lg:col-span-1">
                                <IngestionHistory
                                    records={history}
                                    isLoading={historyLoading}
                                    onRefresh={refreshHistory}
                                />
                            </div>
                        </div>

                        {/* Help Section */}
                        <div className="bg-surface-light border border-border-light rounded p-4">
                            <h3 className="text-xs font-bold text-text-main uppercase tracking-wide flex items-center gap-2 mb-3">
                                <span className="material-symbols-outlined text-text-sub text-[16px]">help</span>
                                File Requirements
                            </h3>
                            <div className="grid grid-cols-3 gap-4 text-xs">
                                <div className="bg-white p-3 rounded border border-border-light">
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="material-symbols-outlined text-amber-600 text-[16px]">report_problem</span>
                                        <span className="font-medium text-text-main">Issues</span>
                                    </div>
                                    <ul className="text-text-sub space-y-1">
                                        <li>4 Excel files (.xlsx)</li>
                                        <li>Minimum 5KB each</li>
                                    </ul>
                                </div>
                                <div className="bg-white p-3 rounded border border-border-light">
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="material-symbols-outlined text-blue-600 text-[16px]">verified_user</span>
                                        <span className="font-medium text-text-main">Controls</span>
                                    </div>
                                    <ul className="text-text-sub space-y-1">
                                        <li>1 Excel file (.xlsx)</li>
                                        <li>Minimum 5KB</li>
                                    </ul>
                                </div>
                                <div className="bg-white p-3 rounded border border-border-light">
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="material-symbols-outlined text-green-600 text-[16px]">task_alt</span>
                                        <span className="font-medium text-text-main">Actions</span>
                                    </div>
                                    <ul className="text-text-sub space-y-1">
                                        <li>1 Excel file (.xlsx)</li>
                                        <li>Minimum 5KB</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
        </main>
    );
};

export default Pipelines;
