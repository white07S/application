import React, { useState, useEffect, useRef } from 'react';
import { SearchMode, SemanticFeature, SEMANTIC_FEATURES, ControlsAction } from '../types';

interface Props {
    value: string;
    searchMode: SearchMode;
    searchTags: string[];
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
    keyword: 'Type keyword, press Enter or |',
    semantic: 'Describe what you\'re looking for, press Enter or |',
    hybrid: 'Type keyword or description, press Enter or |',
};

const DELIMITER_RE = /[|,;]/;

export const ControlsSearchBar: React.FC<Props> = ({ value, searchMode, searchTags, semanticFeatures, dispatch }) => {
    // ID mode: local text with debounce
    const [localValue, setLocalValue] = useState(value);
    // Tag mode: current text being typed (not yet committed)
    const [tagInput, setTagInput] = useState('');

    const [modeOpen, setModeOpen] = useState(false);
    const [featuresOpen, setFeaturesOpen] = useState(false);
    const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
    const modeRef = useRef<HTMLDivElement>(null);
    const featuresRef = useRef<HTMLDivElement>(null);
    const tagInputRef = useRef<HTMLInputElement>(null);

    const isIdMode = searchMode === 'id';

    // Sync external value for ID mode
    useEffect(() => { setLocalValue(value); }, [value]);

    // ID mode: debounced text input
    const handleIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const v = e.target.value;
        setLocalValue(v);
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => dispatch({ type: 'SET_SEARCH', payload: v }), 200);
    };

    useEffect(() => () => clearTimeout(timerRef.current), []);

    // Tag mode: commit current input as a tag
    const commitTag = (text: string) => {
        const trimmed = text.trim();
        if (!trimmed) return;
        dispatch({ type: 'SET_SEARCH_TAGS', payload: [...searchTags, trimmed] });
    };

    // Tag mode: handle input changes — check for delimiters
    const handleTagInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const v = e.target.value;
        if (DELIMITER_RE.test(v)) {
            // Split on any delimiter, commit non-empty parts
            const parts = v.split(DELIMITER_RE).map(s => s.trim()).filter(Boolean);
            if (parts.length > 0) {
                dispatch({ type: 'SET_SEARCH_TAGS', payload: [...searchTags, ...parts] });
            }
            setTagInput('');
        } else {
            setTagInput(v);
        }
    };

    // Tag mode: handle key events
    const handleTagKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            if (tagInput.trim()) {
                commitTag(tagInput);
                setTagInput('');
            }
        } else if (e.key === 'Backspace' && tagInput === '' && searchTags.length > 0) {
            dispatch({ type: 'SET_SEARCH_TAGS', payload: searchTags.slice(0, -1) });
        }
    };

    // Tag mode: commit on blur
    const handleTagBlur = () => {
        if (tagInput.trim()) {
            commitTag(tagInput);
            setTagInput('');
        }
    };

    const removeTag = (index: number) => {
        dispatch({ type: 'SET_SEARCH_TAGS', payload: searchTags.filter((_, i) => i !== index) });
    };

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
        <div className="flex items-stretch gap-0 min-h-[32px]">
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

            {/* Search input area */}
            {isIdMode ? (
                /* ID mode: plain text input */
                <div className="flex-1 flex items-center border border-border-light bg-white min-w-0">
                    <span className="material-symbols-outlined text-[16px] text-text-sub pl-2 flex-shrink-0">search</span>
                    <input
                        type="text"
                        value={localValue}
                        onChange={handleIdChange}
                        placeholder={PLACEHOLDER.id}
                        className="h-full flex-1 text-xs px-2 py-0 border-none focus:ring-0 focus:outline-none bg-transparent text-text-main placeholder-text-sub min-w-0"
                    />
                </div>
            ) : (
                /* Tag mode: chip input */
                <div
                    className="flex-1 flex items-center flex-wrap gap-1 border border-border-light bg-white min-w-0 px-2 py-1 cursor-text"
                    onClick={() => tagInputRef.current?.focus()}
                >
                    <span className="material-symbols-outlined text-[16px] text-text-sub flex-shrink-0">search</span>
                    {searchTags.map((tag, i) => (
                        <span
                            key={i}
                            className="inline-flex items-center gap-0.5 bg-primary/10 text-primary text-[11px] font-medium pl-2 pr-1 py-0.5 rounded select-none"
                        >
                            {tag}
                            <button
                                onClick={(e) => { e.stopPropagation(); removeTag(i); }}
                                className="hover:text-red-500 transition-colors ml-0.5 flex items-center"
                                tabIndex={-1}
                            >
                                <span className="material-symbols-outlined text-[12px]">close</span>
                            </button>
                        </span>
                    ))}
                    <input
                        ref={tagInputRef}
                        type="text"
                        value={tagInput}
                        onChange={handleTagInputChange}
                        onKeyDown={handleTagKeyDown}
                        onBlur={handleTagBlur}
                        placeholder={searchTags.length === 0 ? PLACEHOLDER[searchMode] : ''}
                        className="flex-1 min-w-[80px] text-xs px-1 py-0 border-none focus:ring-0 focus:outline-none bg-transparent text-text-main placeholder-text-sub"
                    />
                </div>
            )}

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
                                    {semanticFeatures.size} of {SEMANTIC_FEATURES.length} vector fields active
                                </span>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Right cap — round the corner */}
            {!showFeatures && (
                <div className="h-full border-r border-y border-border-light rounded-r w-0" />
            )}
            {showFeatures && (
                <div className="rounded-r" />
            )}
        </div>
    );
};
