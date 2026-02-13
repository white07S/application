import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RelationshipExpansion } from '../types';

interface RelationshipRowProps {
    recordId: string;
    onExpand: (recordId: string) => Promise<RelationshipExpansion | null>;
}

const RelationshipRow: React.FC<RelationshipRowProps> = ({ recordId, onExpand }) => {
    const navigate = useNavigate();
    const [expanded, setExpanded] = useState(false);
    const [data, setData] = useState<RelationshipExpansion | null>(null);
    const [loading, setLoading] = useState(false);

    const handleToggle = async () => {
        if (expanded) {
            setExpanded(false);
            return;
        }

        setLoading(true);
        const result = await onExpand(recordId);
        setData(result);
        setExpanded(true);
        setLoading(false);
    };

    const navigateToTable = (tableName: string) => {
        navigate(`/devdata/${tableName}`);
    };

    const renderRecordPreview = (record: Record<string, any> | null, table: string, label: string) => {
        if (!record) return <span className="text-text-sub text-xs italic">Not found</span>;

        const displayKeys = Object.keys(record).filter(k => k !== 'id').slice(0, 4);
        return (
            <div className="bg-white border border-border-light rounded p-2">
                <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-medium text-text-sub uppercase tracking-wide">{label}</span>
                    <button
                        onClick={() => navigateToTable(table)}
                        className="text-[10px] text-primary hover:underline flex items-center gap-0.5"
                    >
                        <span className="material-symbols-outlined text-[12px]">open_in_new</span>
                        {table}
                    </button>
                </div>
                <div className="text-[10px] font-mono text-text-sub">
                    {record.id && (
                        <div className="mb-1 text-text-main font-medium">{String(record.id)}</div>
                    )}
                    {displayKeys.map(key => (
                        <div key={key} className="truncate">
                            <span className="text-text-sub">{key}:</span>{' '}
                            <span className="text-text-main">{formatValue(record[key])}</span>
                        </div>
                    ))}
                    {Object.keys(record).length > 5 && (
                        <div className="text-text-sub mt-0.5">+{Object.keys(record).length - 5} more fields</div>
                    )}
                </div>
            </div>
        );
    };

    return (
        <div>
            <button
                onClick={handleToggle}
                className="w-full flex items-center gap-1 px-2 py-1 text-xs text-primary hover:bg-surface-light rounded transition-colors"
            >
                {loading ? (
                    <span className="material-symbols-outlined text-[14px] animate-spin">refresh</span>
                ) : (
                    <span className="material-symbols-outlined text-[14px]">
                        {expanded ? 'expand_less' : 'expand_more'}
                    </span>
                )}
                <span>{expanded ? 'Collapse' : 'Expand'} relationship</span>
            </button>

            {expanded && data && (
                <div className="mt-1 ml-4 space-y-2 pb-2">
                    {/* Edge metadata */}
                    <div className="bg-surface-alt border border-border-light rounded p-2">
                        <div className="text-[10px] font-medium text-text-sub uppercase tracking-wide mb-1">Edge Data</div>
                        <div className="text-[10px] font-mono space-y-0.5">
                            {Object.entries(data.edge)
                                .filter(([k]) => k !== 'in' && k !== 'out' && k !== 'id')
                                .map(([key, val]) => (
                                    <div key={key}>
                                        <span className="text-text-sub">{key}:</span>{' '}
                                        <span className="text-text-main">{formatValue(val)}</span>
                                    </div>
                                ))}
                        </div>
                    </div>

                    {/* IN / OUT records side by side */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {renderRecordPreview(data.in_record, data.in_table, `IN (${data.in_table})`)}
                        {renderRecordPreview(data.out_record, data.out_table, `OUT (${data.out_table})`)}
                    </div>
                </div>
            )}
        </div>
    );
};

function formatValue(val: any): string {
    if (val === null || val === undefined) return 'null';
    if (typeof val === 'object') {
        if (val.truncated && val.dimensions) return `[${val.dimensions}-dim vector]`;
        return JSON.stringify(val).substring(0, 80);
    }
    const str = String(val);
    return str.length > 80 ? str.substring(0, 77) + '...' : str;
}

export default RelationshipRow;
