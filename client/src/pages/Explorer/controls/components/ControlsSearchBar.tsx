import React, { useState, useEffect, useRef } from 'react';
import { SearchMode, SemanticFeature, SEMANTIC_FEATURES, ControlsAction } from '../types';

interface Props {
    value: string;
    searchMode: SearchMode;
    semanticFeatures: Set<SemanticFeature>;
    dispatch: React.Dispatch<ControlsAction>;
}

const MODE_OPTIONS: { key: SearchMode; label: string; icon: string; description: string }[] = [
    { key: 'id', label: 'Control ID', icon: 'tag', description: 'Exact match on control ID' },
    { key: 'keyword', label: 'Keyword', icon: 'text_fields', description: 'Search across title, description, owner' },
    { key: 'semantic', label: 'Semantic', icon: 'psychology', description: 'Find similar controls via embeddings' },
    { key: 'hybrid', label: 'Hybrid', icon: 'join', description: 'Keyword + Semantic combined' },
];

const PLACEHOLDER: Record<SearchMode, string> = {
    id: 'Enter control ID (e.g. CTRL-001)...',
    keyword: 'Search by title, description, owner...',
    semantic: 'Describe the control you\'re looking for...',
    hybrid: 'Search by keywords or describe what you need...',
};

export const ControlsSearchBar: React.FC<Props> = ({ value, searchMode, semanticFeatures, dispatch }) => {
    const [localValue, setLocalValue] = useState(value);
    const [modeOpen, setModeOpen] = useState(false);
    const [featuresOpen, setFeaturesOpen] = useState(false);
    const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
    const modeRef = useRef<HTMLDivElement>(null);
    const featuresRef = useRef<HTMLDivElement>(null);

    useEffect(() => { setLocalValue(value); }, [value]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const v = e.target.value;
        setLocalValue(v);
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => dispatch({ type: 'SET_SEARCH', payload: v }), 200);
    };

    useEffect(() => () => clearTimeout(timerRef.current), []);

    // Close dropdowns on outside click
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (modeRef.current && !modeRef.current.contains(e.target as Node)) setModeOpen(false);
            if (featuresRef.current && !featuresRef.current.contains(e.target as Node)) setFeaturesOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const currentMode = MODE_OPTIONS.find((m) => m.key === searchMode)!;
    const showFeatures = searchMode === 'semantic' || searchMode === 'hybrid';

    return (
        <div className="flex items-stretch gap-0">
            {/* Mode selector dropdown */}
            <div ref={modeRef} className="relative flex-shrink-0">
                <button
                    onClick={() => { setModeOpen(!modeOpen); setFeaturesOpen(false); }}
                    className="flex items-center gap-1.5 h-full px-2.5 border border-r-0 border-border-light rounded-l bg-surface-light hover:bg-surface-hover text-text-main transition-colors"
                >
                    <span className="material-symbols-outlined text-[14px] text-text-sub">{currentMode.icon}</span>
                    <span className="text-xs font-medium whitespace-nowrap">{currentMode.label}</span>
                    <span className={`material-symbols-outlined text-[12px] text-text-sub transition-transform ${modeOpen ? 'rotate-180' : ''}`}>
                        expand_more
                    </span>
                </button>
                {modeOpen && (
                    <div className="absolute top-full left-0 mt-1 bg-white border border-border-light rounded shadow-floating z-20 min-w-[200px]">
                        {MODE_OPTIONS.map((opt) => (
                            <button
                                key={opt.key}
                                onClick={() => {
                                    dispatch({ type: 'SET_SEARCH_MODE', payload: opt.key });
                                    setModeOpen(false);
                                }}
                                className={`w-full flex items-start gap-2 px-3 py-2 text-left hover:bg-surface-light transition-colors ${
                                    searchMode === opt.key ? 'bg-primary/5' : ''
                                }`}
                            >
                                <span className={`material-symbols-outlined text-[16px] mt-0.5 ${searchMode === opt.key ? 'text-primary' : 'text-text-sub'}`}>
                                    {opt.icon}
                                </span>
                                <div>
                                    <span className={`text-xs font-medium block ${searchMode === opt.key ? 'text-primary' : 'text-text-main'}`}>
                                        {opt.label}
                                    </span>
                                    <span className="text-[10px] text-text-sub">{opt.description}</span>
                                </div>
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* Search input */}
            <div className="flex-1 flex items-center border border-border-light bg-white min-w-0">
                <span className="material-symbols-outlined text-[16px] text-text-sub pl-2 flex-shrink-0">search</span>
                <input
                    type="text"
                    value={localValue}
                    onChange={handleChange}
                    placeholder={PLACEHOLDER[searchMode]}
                    className="flex-1 text-xs px-2 py-1.5 border-none focus:ring-0 focus:outline-none bg-transparent text-text-main placeholder-text-sub min-w-0"
                />
            </div>

            {/* Semantic feature toggles (only for semantic/hybrid) */}
            {showFeatures && (
                <div ref={featuresRef} className="relative flex-shrink-0">
                    <button
                        onClick={() => { setFeaturesOpen(!featuresOpen); setModeOpen(false); }}
                        className="flex items-center gap-1 h-full px-2.5 border border-l-0 border-border-light bg-surface-light hover:bg-surface-hover text-text-main transition-colors"
                        title="Select embedding features"
                    >
                        <span className="material-symbols-outlined text-[14px] text-text-sub">tune</span>
                        <span className="text-[10px] font-medium text-primary">{semanticFeatures.size}</span>
                        <span className={`material-symbols-outlined text-[12px] text-text-sub transition-transform ${featuresOpen ? 'rotate-180' : ''}`}>
                            expand_more
                        </span>
                    </button>
                    {featuresOpen && (
                        <div className="absolute top-full right-0 mt-1 bg-white border border-border-light rounded shadow-floating z-20 min-w-[220px] p-2">
                            <div className="text-[10px] text-text-sub uppercase font-medium tracking-wide px-1 pb-1.5 border-b border-border-light mb-1.5">
                                Search across features
                            </div>
                            {SEMANTIC_FEATURES.map((feat) => (
                                <label
                                    key={feat.key}
                                    className="flex items-center gap-2 px-1 py-1 rounded hover:bg-surface-light cursor-pointer"
                                >
                                    <input
                                        type="checkbox"
                                        checked={semanticFeatures.has(feat.key)}
                                        onChange={() => dispatch({ type: 'TOGGLE_SEMANTIC_FEATURE', payload: feat.key })}
                                        className="h-3 w-3 rounded border-gray-300 text-primary focus:ring-primary/20"
                                    />
                                    <span className="text-xs text-text-main">{feat.label}</span>
                                </label>
                            ))}
                            <div className="mt-1.5 pt-1.5 border-t border-border-light px-1">
                                <span className="text-[10px] text-text-sub italic flex items-center gap-1">
                                    <span className="material-symbols-outlined text-[10px]">info</span>
                                    Qdrant backend not connected
                                </span>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Right cap — round the corner */}
            {!showFeatures && (
                <div className="border-r border-y border-border-light rounded-r w-0" />
            )}
            {showFeatures && (
                <div className="rounded-r" />
            )}
        </div>
    );
};
