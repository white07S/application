import React from 'react';
import EmbeddingCell from './EmbeddingCell';

interface RecordDetailProps {
    record: Record<string, any>;
    onClose: () => void;
}

const RecordDetail: React.FC<RecordDetailProps> = ({ record, onClose }) => {
    return (
        <div className="bg-white border border-border-light rounded shadow-card">
            <div className="flex items-center justify-between px-3 py-2 border-b border-border-light bg-surface-light/50">
                <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-[16px] text-text-sub">description</span>
                    <span className="text-xs font-medium text-text-main">
                        {record.id ? String(record.id) : 'Record Detail'}
                    </span>
                </div>
                <button
                    onClick={onClose}
                    className="p-1 rounded hover:bg-surface-hover transition-colors"
                >
                    <span className="material-symbols-outlined text-[16px] text-text-sub">close</span>
                </button>
            </div>
            <div className="p-3 max-h-[60vh] overflow-y-auto">
                <table className="w-full">
                    <tbody className="text-xs">
                        {Object.entries(record).map(([key, value]) => (
                            <tr key={key} className="border-b border-border-light/50 last:border-0">
                                <td className="py-1.5 pr-3 font-medium text-text-sub align-top whitespace-nowrap w-1/4">
                                    {key}
                                </td>
                                <td className="py-1.5 font-mono text-text-main break-all">
                                    {renderValue(key, value)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

function renderValue(key: string, value: any): React.ReactNode {
    if (value === null || value === undefined) {
        return <span className="text-text-sub italic">null</span>;
    }

    if (typeof value === 'object' && value.truncated && value.dimensions) {
        return <EmbeddingCell value={value} fieldName={key} />;
    }

    if (typeof value === 'object') {
        return (
            <pre className="text-[10px] bg-surface-alt p-1.5 rounded overflow-x-auto max-h-40">
                {JSON.stringify(value, null, 2)}
            </pre>
        );
    }

    if (typeof value === 'boolean') {
        return (
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${value ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                {String(value)}
            </span>
        );
    }

    return <span>{String(value)}</span>;
}

export default RecordDetail;
