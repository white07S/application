import React from 'react';

interface Props {
    label: string;
    count: number;
    expanded: boolean;
    onToggle: () => void;
}

export const GroupHeader: React.FC<Props> = ({ label, count, expanded, onToggle }) => {
    return (
        <button
            onClick={onToggle}
            className="w-full flex items-center gap-2 py-2 border-b border-border-light group"
        >
            <span
                className={`material-symbols-outlined text-[16px] text-text-sub transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
            >
                expand_more
            </span>
            <span className="text-sm font-medium text-text-main">{label}</span>
            <span className="text-[10px] bg-surface-light text-text-sub px-1.5 py-0.5 rounded-sm">
                {count} control{count !== 1 ? 's' : ''}
            </span>
        </button>
    );
};
