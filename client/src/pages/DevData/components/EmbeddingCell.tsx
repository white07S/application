import React, { useState } from 'react';

interface EmbeddingValue {
    preview: number[];
    dimensions: number;
    truncated: boolean;
}

interface EmbeddingCellProps {
    value: EmbeddingValue;
    fieldName: string;
}

const EmbeddingCell: React.FC<EmbeddingCellProps> = ({ value, fieldName }) => {
    const [expanded, setExpanded] = useState(false);

    if (!value || !value.truncated) {
        return <span className="text-text-sub text-xs font-mono">null</span>;
    }

    return (
        <div className="inline-flex items-center gap-1">
            <button
                onClick={() => setExpanded(!expanded)}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-surface-alt rounded text-xs font-mono text-text-sub hover:text-text-main hover:bg-surface-hover transition-colors"
                title={`${fieldName}: ${value.dimensions}-dimensional vector`}
            >
                <span className="material-symbols-outlined text-[12px]">data_array</span>
                <span>{value.dimensions}-dim</span>
            </button>
            {expanded && (
                <span className="text-[10px] font-mono text-text-sub">
                    [{value.preview.map(v => v.toFixed(4)).join(', ')}, ...]
                </span>
            )}
        </div>
    );
};

export default EmbeddingCell;
