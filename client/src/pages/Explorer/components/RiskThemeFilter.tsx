import React, { useState, useMemo } from 'react';
import { RiskTaxonomy, RiskTheme } from '../types';

interface RiskThemeFilterProps {
    taxonomies: RiskTaxonomy[];
    selected: Set<string>;
    onToggle: (id: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
    Active: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    Expired: 'bg-amber-50 text-amber-600 border-amber-200',
};

export const RiskThemeFilter: React.FC<RiskThemeFilterProps> = ({
    taxonomies,
    selected,
    onToggle,
}) => {
    const [search, setSearch] = useState('');

    // Flatten all themes (active + expired children) into a single list
    const allThemes = useMemo(() => {
        const themes: RiskTheme[] = [];
        for (const tax of taxonomies) {
            for (const theme of tax.themes) {
                themes.push(theme);
                if (theme.children) {
                    for (const child of theme.children) {
                        themes.push(child);
                    }
                }
            }
        }
        return themes;
    }, [taxonomies]);

    const filtered = useMemo(() => {
        if (!search) return allThemes;
        const lower = search.toLowerCase();
        return allThemes.filter((t) => t.name.toLowerCase().includes(lower));
    }, [allThemes, search]);

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
                {filtered.map((theme) => (
                    <label
                        key={theme.id}
                        className="flex items-center gap-1.5 py-0.5 px-1 hover:bg-surface-light cursor-pointer"
                    >
                        <input
                            type="checkbox"
                            checked={selected.has(theme.id)}
                            onChange={() => onToggle(theme.id)}
                            className="w-3 h-3 rounded-sm border-border-light text-primary focus:ring-primary/20 focus:ring-1 flex-shrink-0 accent-primary"
                        />
                        <span
                            className={`text-[8px] font-semibold px-1 py-px rounded border flex-shrink-0 leading-tight ${STATUS_COLORS[theme.status] || 'bg-gray-50 text-gray-400 border-gray-200'}`}
                        >
                            {theme.status === 'Expired' ? 'EXP' : 'ACT'}
                        </span>
                        <span className="text-xs text-text-main truncate" title={theme.name}>
                            {theme.name}
                        </span>
                    </label>
                ))}
            </div>
        </div>
    );
};
