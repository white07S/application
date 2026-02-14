import React, { useState, useMemo } from 'react';
import { FlatItem } from '../types';

interface FlatListFilterProps {
    items: FlatItem[];
    selected: Set<string>;
    onToggle: (id: string) => void;
    onSearchChange?: (query: string) => void;
    loading?: boolean;
    hasMore?: boolean;
    placeholder?: string;
}

export const FlatListFilter: React.FC<FlatListFilterProps> = ({
    items,
    selected,
    onToggle,
    onSearchChange,
    loading = false,
    hasMore = false,
    placeholder = 'Search...',
}) => {
    const [search, setSearch] = useState('');

    // If onSearchChange is provided (server-side search), use items as-is
    // Otherwise, filter locally (for small datasets like AUs)
    const filtered = useMemo(() => {
        if (onSearchChange) return items;
        if (!search) return items;
        const lower = search.toLowerCase();
        return items.filter(
            (item) =>
                item.label.toLowerCase().includes(lower) ||
                item.description?.toLowerCase().includes(lower)
        );
    }, [items, search, onSearchChange]);

    const handleSearchChange = (value: string) => {
        setSearch(value);
        if (onSearchChange) {
            onSearchChange(value);
        }
    };

    return (
        <div className="px-1">
            <div className="relative mb-1.5">
                <span className="material-symbols-outlined text-[14px] text-text-sub absolute left-2 top-1/2 -translate-y-1/2">
                    search
                </span>
                <input
                    type="text"
                    value={search}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    placeholder={placeholder}
                    className="w-full pl-7 pr-2 py-1 text-xs border border-border-light bg-white text-text-main placeholder:text-text-sub/50 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 rounded-sm"
                />
            </div>
            <div className="max-h-[200px] overflow-y-auto">
                {loading ? (
                    <div className="py-3 flex items-center justify-center gap-1.5">
                        <span className="material-symbols-outlined text-[14px] text-text-sub animate-spin">
                            progress_activity
                        </span>
                        <span className="text-[10px] text-text-sub">Loading...</span>
                    </div>
                ) : (
                    <>
                        {filtered.length === 0 && (
                            <p className="text-[10px] text-text-sub py-2 px-1">No results</p>
                        )}
                        {filtered.map((item) => (
                            <label
                                key={item.id}
                                className="flex items-center gap-1.5 py-1 px-1 hover:bg-surface-light cursor-pointer group"
                            >
                                <input
                                    type="checkbox"
                                    checked={selected.has(item.id)}
                                    onChange={() => onToggle(item.id)}
                                    className="w-3 h-3 rounded-sm border-border-light text-primary focus:ring-primary/20 focus:ring-1 flex-shrink-0 accent-primary"
                                />
                                <div className="flex-1 min-w-0">
                                    <span className="text-xs text-text-main truncate block">
                                        {item.label}
                                    </span>
                                    {item.description && (
                                        <span className="text-[10px] text-text-sub truncate block">
                                            {item.description}
                                        </span>
                                    )}
                                </div>
                            </label>
                        ))}
                        {hasMore && (
                            <p className="text-[10px] text-text-sub py-1 px-1 text-center">
                                Showing first {filtered.length} results. Refine your search.
                            </p>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};
