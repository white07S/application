import React from 'react';

interface Props {
    label: string;
    oldValue: unknown;
    newValue: unknown;
    fieldType: 'text' | 'bool' | 'list' | 'long';
}

const stringify = (v: unknown, fieldType: string): string => {
    if (v === null || v === undefined) return '—';
    if (fieldType === 'bool') return v ? 'Yes' : 'No';
    if (fieldType === 'list' && Array.isArray(v)) return v.length ? v.join(', ') : '—';
    if (fieldType === 'text' && typeof v === 'string' && v.includes('T')) {
        // Attempt date formatting
        try {
            return new Date(v).toLocaleString('en-GB', {
                day: '2-digit', month: 'short', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
            });
        } catch { /* fall through */ }
    }
    return String(v);
};

export const DiffField: React.FC<Props> = ({ label, oldValue, newValue, fieldType }) => {
    const oldStr = stringify(oldValue, fieldType);
    const newStr = stringify(newValue, fieldType);
    const changed = oldStr !== newStr;

    return (
        <div className={`py-1 px-2 rounded text-[11px] ${changed ? 'bg-amber-50/50' : ''}`}>
            <div className="text-[10px] text-text-sub font-medium mb-0.5">{label}</div>
            {fieldType === 'long' ? (
                <div className="grid grid-cols-2 gap-2">
                    <div className={`p-1.5 rounded text-[10px] leading-relaxed whitespace-pre-wrap ${
                        changed ? 'bg-red-50/60 text-text-main' : 'bg-surface-light text-text-sub'
                    }`}>
                        {oldStr}
                    </div>
                    <div className={`p-1.5 rounded text-[10px] leading-relaxed whitespace-pre-wrap ${
                        changed ? 'bg-green-50/60 text-text-main' : 'bg-surface-light text-text-sub'
                    }`}>
                        {newStr}
                    </div>
                </div>
            ) : (
                <div className="flex items-center gap-2">
                    <span className={`${changed ? 'line-through text-red-400' : 'text-text-sub'}`}>{oldStr}</span>
                    {changed && (
                        <>
                            <span className="material-symbols-outlined text-[12px] text-text-sub">arrow_forward</span>
                            <span className="text-green-700 font-medium">{newStr}</span>
                        </>
                    )}
                </div>
            )}
        </div>
    );
};
