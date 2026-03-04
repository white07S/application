import React, { useState, useMemo } from 'react';

interface FilterSectionProps {
    icon: string;
    title: string;
    count: number;
    onClear: () => void;
    children: React.ReactNode;
    defaultExpanded?: boolean;
    loading?: boolean;
    /** Controlled mode: parent manages expanded state */
    expanded?: boolean;
    onToggle?: () => void;
    /** ISO timestamp of when the source data was last updated. */
    lastUpdated?: string | null;
}

function formatDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function isStale(iso: string): boolean {
    const d = new Date(iso);
    const now = new Date();
    const oneMonthAgo = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
    return d < oneMonthAgo;
}

export const FilterSection: React.FC<FilterSectionProps> = ({
    icon,
    title,
    count,
    onClear,
    children,
    defaultExpanded = false,
    loading = false,
    expanded: controlledExpanded,
    onToggle,
    lastUpdated,
}) => {
    const [internalExpanded, setInternalExpanded] = useState(defaultExpanded);
    const expanded = controlledExpanded !== undefined ? controlledExpanded : internalExpanded;
    const toggle = onToggle || (() => setInternalExpanded((v) => !v));

    const stale = useMemo(() => lastUpdated ? isStale(lastUpdated) : false, [lastUpdated]);

    return (
        <div className="py-2">
            <button
                onClick={toggle}
                className="w-full flex items-center gap-1.5 py-1 group"
            >
                <span className="material-symbols-outlined text-[14px] text-text-sub">
                    {icon}
                </span>
                <span className="text-[10px] font-bold text-text-sub uppercase tracking-wider flex-1 text-left">
                    {title}
                </span>
                {loading && (
                    <span className="material-symbols-outlined text-[12px] text-text-sub animate-spin">
                        progress_activity
                    </span>
                )}
                {count > 0 && (
                    <span className="bg-primary/10 text-primary text-[10px] font-semibold px-1.5 py-0.5 rounded-sm min-w-[18px] text-center">
                        {count}
                    </span>
                )}
                {count > 0 && (
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onClear();
                        }}
                        className="text-[10px] text-text-sub hover:text-primary px-1"
                        title="Clear"
                    >
                        <span className="material-symbols-outlined text-[12px]">close</span>
                    </button>
                )}
                <span
                    className={`material-symbols-outlined text-[14px] text-text-sub transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
                >
                    expand_more
                </span>
            </button>
            {lastUpdated && (
                <div className={`flex items-center gap-1 px-0.5 mt-0.5 ${stale ? 'text-amber-600' : 'text-text-sub'}`}>
                    {stale && (
                        <span className="material-symbols-outlined text-[12px] text-amber-500">warning</span>
                    )}
                    <span className="text-[9px]">
                        Updated: {formatDate(lastUpdated)}
                    </span>
                    {stale && (
                        <span className="text-[9px] font-medium text-amber-600">
                            (stale)
                        </span>
                    )}
                </div>
            )}
            <div
                className={`overflow-hidden transition-all duration-200 ease-out ${expanded ? 'max-h-[300px] opacity-100 mt-1' : 'max-h-0 opacity-0'}`}
            >
                {children}
            </div>
        </div>
    );
};
