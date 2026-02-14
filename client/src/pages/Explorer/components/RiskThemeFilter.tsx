import React, { useState, useMemo } from 'react';
import { RiskTaxonomy } from '../types';

interface RiskThemeFilterProps {
    taxonomies: RiskTaxonomy[];
    selected: Set<string>;
    onToggle: (id: string) => void;
}

export const RiskThemeFilter: React.FC<RiskThemeFilterProps> = ({
    taxonomies,
    selected,
    onToggle,
}) => {
    const [search, setSearch] = useState('');

    const filtered = useMemo(() => {
        if (!search) return taxonomies;
        const lower = search.toLowerCase();
        return taxonomies
            .map((tax) => ({
                ...tax,
                themes: tax.themes.filter((t) => t.name.toLowerCase().includes(lower)),
            }))
            .filter((tax) => tax.themes.length > 0 || tax.name.toLowerCase().includes(lower));
    }, [taxonomies, search]);

    return (
        <div className="px-1">
            <div className="relative mb-1.5">
                <span className="material-symbols-outlined text-[14px] text-text-sub absolute left-2 top-1/2 -translate-y-1/2">
                    search
                </span>
                <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search themes..."
                    className="w-full pl-7 pr-2 py-1 text-xs border border-border-light bg-white text-text-main placeholder:text-text-sub/50 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 rounded-sm"
                />
            </div>
            <div className="max-h-[220px] overflow-y-auto">
                {filtered.length === 0 && (
                    <p className="text-[10px] text-text-sub py-2 px-1">No results</p>
                )}
                {filtered.map((taxonomy) => (
                    <div key={taxonomy.id} className="mb-2">
                        <div className="text-[10px] font-bold text-text-sub uppercase tracking-wider px-1 py-0.5">
                            {taxonomy.name}
                        </div>
                        {taxonomy.themes.map((theme) => (
                            <label
                                key={theme.id}
                                className="flex items-center gap-1.5 py-0.5 px-1 pl-3 hover:bg-surface-light cursor-pointer"
                            >
                                <input
                                    type="checkbox"
                                    checked={selected.has(theme.id)}
                                    onChange={() => onToggle(theme.id)}
                                    className="w-3 h-3 rounded-sm border-border-light text-primary focus:ring-primary/20 focus:ring-1 flex-shrink-0 accent-primary"
                                />
                                <span className="text-xs text-text-main">
                                    {theme.name}
                                </span>
                            </label>
                        ))}
                    </div>
                ))}
            </div>
        </div>
    );
};
