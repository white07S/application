import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PaginatedRecords, RelationshipExpansion, getCategoryMeta } from '../types';
import EmbeddingCell from './EmbeddingCell';
import RelationshipRow from './RelationshipRow';
import RecordDetail from './RecordDetail';
import Pagination from './Pagination';

interface TableViewerProps {
    data: PaginatedRecords;
    loading: boolean;
    page: number;
    pageSize: number;
    onPageChange: (page: number) => void;
    onPageSizeChange: (size: number) => void;
    onRefresh: () => void;
    onExpandRelationship: (recordId: string) => Promise<RelationshipExpansion | null>;
}

/** Detect if a value is a truncated embedding (from server-side truncation). */
function isEmbeddingValue(value: any): boolean {
    return typeof value === 'object' && value !== null && value.truncated === true && typeof value.dimensions === 'number';
}

const TableViewer: React.FC<TableViewerProps> = ({
    data,
    loading,
    page,
    pageSize,
    onPageChange,
    onPageSizeChange,
    onRefresh,
    onExpandRelationship,
}) => {
    const navigate = useNavigate();
    const [selectedRecord, setSelectedRecord] = useState<Record<string, any> | null>(null);

    if (!data || data.records.length === 0) {
        return (
            <div className="bg-white border border-border-light rounded shadow-card">
                <div className="px-3 py-2 border-b border-border-light bg-surface-light/50">
                    <h2 className="text-sm font-medium text-text-main">{data?.table_name || 'No table'}</h2>
                </div>
                <div className="p-8 text-center text-xs text-text-sub">
                    <span className="material-symbols-outlined text-[24px] mb-2 block">table_rows</span>
                    No records found
                </div>
            </div>
        );
    }

    const columns = Object.keys(data.records[0]);
    // Derive category from table name using the same pattern-based logic as the server
    const categoryKey = data.table_name.includes('_ref_') ? 'reference'
        : data.table_name.includes('_rel_') ? 'relation'
        : data.table_name.includes('_model_') ? 'model'
        : data.table_name.endsWith('_versions') ? 'version'
        : data.table_name.includes('_main') ? 'main'
        : 'other';
    const categoryMeta = getCategoryMeta(categoryKey);

    const isLinkColumn = (col: string) => col === 'in' || col === 'out';

    const handleCellClick = (col: string, value: any) => {
        if (isLinkColumn(col) && value) {
            const tableId = String(value);
            const tablePart = tableId.split(':')[0];
            if (tablePart) {
                navigate(`/devdata/${tablePart}`);
            }
        }
    };

    const renderCell = (col: string, value: any) => {
        if (value === null || value === undefined) {
            return <span className="text-text-sub/50 italic">null</span>;
        }

        // Embedding fields (detected dynamically from server truncation)
        if (isEmbeddingValue(value)) {
            return <EmbeddingCell value={value} fieldName={col} />;
        }

        // Record link columns (in/out for relations)
        if (isLinkColumn(col)) {
            return (
                <button
                    onClick={() => handleCellClick(col, value)}
                    className="text-primary hover:underline text-left"
                >
                    {String(value)}
                </button>
            );
        }

        // ID column
        if (col === 'id') {
            return <span className="font-medium">{String(value)}</span>;
        }

        // Object values
        if (typeof value === 'object') {
            if (isEmbeddingValue(value)) {
                return <EmbeddingCell value={value} fieldName={col} />;
            }
            const str = JSON.stringify(value);
            return (
                <span className="font-mono" title={str}>
                    {str.length > 60 ? str.substring(0, 57) + '...' : str}
                </span>
            );
        }

        // Boolean
        if (typeof value === 'boolean') {
            return (
                <span className={`px-1 py-0.5 rounded text-[10px] font-medium ${value ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                    {String(value)}
                </span>
            );
        }

        const str = String(value);
        return <span title={str.length > 60 ? str : undefined}>{str.length > 60 ? str.substring(0, 57) + '...' : str}</span>;
    };

    return (
        <div className="space-y-3">
            {/* Selected record detail */}
            {selectedRecord && (
                <RecordDetail record={selectedRecord} onClose={() => setSelectedRecord(null)} />
            )}

            {/* Table card */}
            <div className="bg-white border border-border-light rounded shadow-card">
                {/* Header */}
                <div className="flex items-center justify-between px-3 py-2 border-b border-border-light bg-surface-light/50">
                    <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-[16px] text-text-sub">{categoryMeta?.icon || 'table_chart'}</span>
                        <h2 className="text-sm font-medium text-text-main">{data.table_name}</h2>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-alt text-text-sub">
                            {data.total} records
                        </span>
                        {data.is_relation && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600">relation</span>
                        )}
                        {data.has_embeddings && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600">embeddings</span>
                        )}
                    </div>
                    <button
                        onClick={onRefresh}
                        className="p-1 rounded hover:bg-surface-hover transition-colors"
                        title="Refresh"
                    >
                        <span className={`material-symbols-outlined text-[16px] text-text-sub ${loading ? 'animate-spin' : ''}`}>refresh</span>
                    </button>
                </div>

                {/* Scrollable table */}
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="bg-surface-alt/50">
                                <th className="px-2 py-1.5 text-left text-[10px] font-medium text-text-sub uppercase tracking-wide border-b border-border-light w-8">
                                    #
                                </th>
                                {columns.map(col => (
                                    <th
                                        key={col}
                                        className="px-2 py-1.5 text-left text-[10px] font-medium text-text-sub uppercase tracking-wide border-b border-border-light whitespace-nowrap"
                                    >
                                        {col}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {data.records.map((record, idx) => (
                                <React.Fragment key={idx}>
                                    <tr
                                        className="hover:bg-surface-light/50 cursor-pointer transition-colors border-b border-border-light/50 last:border-0"
                                        onClick={() => setSelectedRecord(selectedRecord === record ? null : record)}
                                    >
                                        <td className="px-2 py-1.5 text-[10px] text-text-sub">
                                            {(page - 1) * pageSize + idx + 1}
                                        </td>
                                        {columns.map(col => (
                                            <td key={col} className="px-2 py-1.5 text-xs font-mono max-w-[300px] truncate">
                                                {renderCell(col, record[col])}
                                            </td>
                                        ))}
                                    </tr>
                                    {/* Inline relationship expansion for relation tables */}
                                    {data.is_relation && selectedRecord === record && record.id && (
                                        <tr>
                                            <td colSpan={columns.length + 1} className="px-2 py-1 bg-surface-light/30">
                                                <RelationshipRow
                                                    recordId={String(record.id)}
                                                    onExpand={onExpandRelationship}
                                                />
                                            </td>
                                        </tr>
                                    )}
                                </React.Fragment>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Pagination */}
                <Pagination
                    page={page}
                    totalPages={data.total_pages}
                    pageSize={pageSize}
                    total={data.total}
                    onPageChange={onPageChange}
                    onPageSizeChange={onPageSizeChange}
                />
            </div>
        </div>
    );
};

export default TableViewer;
