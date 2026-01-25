import React from 'react';
import { IngestionRecord } from '../types';

interface IngestionHistoryProps {
    records: IngestionRecord[];
    isLoading: boolean;
    onRefresh: () => void;
}

const IngestionHistory: React.FC<IngestionHistoryProps> = ({ records, isLoading, onRefresh }) => {
    const formatDate = (isoString: string): string => {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const formatBytes = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const getDataTypeIcon = (dataType: string): string => {
        switch (dataType) {
            case 'issues': return 'report_problem';
            case 'controls': return 'verified_user';
            case 'actions': return 'task_alt';
            default: return 'description';
        }
    };

    const getDataTypeColor = (dataType: string): string => {
        switch (dataType) {
            case 'issues': return 'text-amber-600 bg-amber-50 border-amber-100';
            case 'controls': return 'text-blue-600 bg-blue-50 border-blue-100';
            case 'actions': return 'text-green-600 bg-green-50 border-green-100';
            default: return 'text-gray-600 bg-gray-50 border-gray-100';
        }
    };

    return (
        <div className="bg-white border border-border-light rounded shadow-card">
            {/* Header */}
            <div className="px-5 py-3 border-b border-border-light bg-surface-light/50 flex items-center justify-between">
                <h2 className="text-xs font-bold text-text-main uppercase tracking-wide flex items-center gap-2">
                    <span className="material-symbols-outlined text-text-sub text-[16px]">history</span>
                    Recent Ingestions
                </h2>
                <button
                    onClick={onRefresh}
                    disabled={isLoading}
                    className="h-6 w-6 flex items-center justify-center text-text-sub hover:text-primary transition-colors border border-border-light rounded bg-white hover:border-primary disabled:opacity-50"
                >
                    <span className={`material-symbols-outlined text-[14px] ${isLoading ? 'animate-spin' : ''}`}>
                        refresh
                    </span>
                </button>
            </div>

            {/* Content */}
            <div className="divide-y divide-border-light">
                {isLoading && records.length === 0 ? (
                    <div className="px-5 py-8 text-center text-text-sub text-xs">
                        <span className="material-symbols-outlined animate-spin text-[20px] mb-2 block">refresh</span>
                        Loading history...
                    </div>
                ) : records.length === 0 ? (
                    <div className="px-5 py-8 text-center text-text-sub text-xs">
                        <span className="material-symbols-outlined text-[24px] mb-2 block text-border-dark">inbox</span>
                        No ingestion records yet
                    </div>
                ) : (
                    records.map((record) => (
                        <div
                            key={record.ingestionId}
                            className="px-5 py-3 hover:bg-surface-light transition-colors"
                        >
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex items-start gap-3 min-w-0">
                                    <div className={`w-8 h-8 rounded flex items-center justify-center border ${getDataTypeColor(record.dataType)}`}>
                                        <span className="material-symbols-outlined text-[16px]">
                                            {getDataTypeIcon(record.dataType)}
                                        </span>
                                    </div>
                                    <div className="min-w-0">
                                        <div className="flex items-center gap-2 mb-0.5">
                                            <span className="font-mono text-xs font-medium text-primary">
                                                {record.ingestionId}
                                            </span>
                                            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium uppercase border ${getDataTypeColor(record.dataType)}`}>
                                                {record.dataType}
                                            </span>
                                        </div>
                                        <div className="text-[11px] text-text-sub">
                                            {record.filesCount} file{record.filesCount > 1 ? 's' : ''} ({formatBytes(record.totalSizeBytes)})
                                        </div>
                                        <div className="text-[10px] text-text-sub/70 mt-0.5 truncate" title={record.fileNames.join(', ')}>
                                            {record.fileNames.slice(0, 2).join(', ')}
                                            {record.fileNames.length > 2 && ` +${record.fileNames.length - 2} more`}
                                        </div>
                                    </div>
                                </div>
                                <div className="text-right shrink-0">
                                    <div className="text-[10px] text-text-sub font-mono">
                                        {formatDate(record.uploadedAt)}
                                    </div>
                                    <div className="text-[10px] text-text-sub/70 mt-0.5">
                                        by {record.uploadedBy}
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default IngestionHistory;
