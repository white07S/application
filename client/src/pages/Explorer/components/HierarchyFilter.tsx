import React, { useState, useMemo, useEffect } from 'react';
import { TreeNode } from '../types';

const TYPE_ABBREV: Record<string, string> = {
    // Functions hierarchy: Group → Division → Unit → Area → Sector → Segment → Function
    group: 'GRP',
    division: 'DIV',
    unit: 'UNT',
    area: 'ARA',
    sector: 'SEC',
    segment: 'SEG',
    function: 'FUN',
    // Locations hierarchy: Location → Region → Sub Region → Country → Company
    location: 'LOC',
    region: 'REG',
    sub_region: 'SUB',
    country: 'CTR',
    company: 'CO',
};

const STATUS_COLORS: Record<string, string> = {
    Active: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    Inactive: 'bg-gray-50 text-gray-400 border-gray-200',
    Deleted: 'bg-red-50 text-red-400 border-red-200',
};

const DEFAULT_STATUS_COLOR = 'bg-gray-50 text-gray-400 border-gray-200';

interface HierarchyFilterProps {
    nodes: TreeNode[];
    selected: Set<string>;
    onToggle: (id: string) => void;
    onExpand?: (nodeId: string, level: number) => void;
    onSearchChange?: (query: string) => void;
    searchLoading?: boolean;
    loadingNodeId?: string | null;
    placeholder?: string;
    loading?: boolean;
}

function flattenVisible(nodes: TreeNode[], expandedSet: Set<string>): TreeNode[] {
    const result: TreeNode[] = [];
    function walk(list: TreeNode[]) {
        for (const node of list) {
            result.push(node);
            if (node.children && expandedSet.has(node.id)) {
                walk(node.children);
            }
        }
    }
    walk(nodes);
    return result;
}

function filterTree(nodes: TreeNode[], query: string): TreeNode[] {
    const lower = query.toLowerCase();
    function matches(node: TreeNode): TreeNode | null {
        const selfMatch = node.label.toLowerCase().includes(lower);
        const childMatches = node.children
            ? node.children.map(matches).filter(Boolean) as TreeNode[]
            : [];

        if (selfMatch || childMatches.length > 0) {
            return {
                ...node,
                children: childMatches.length > 0 ? childMatches : node.children,
            };
        }
        return null;
    }
    return nodes.map(matches).filter(Boolean) as TreeNode[];
}

function getAllIds(nodes: TreeNode[]): Set<string> {
    const ids = new Set<string>();
    function walk(list: TreeNode[]) {
        for (const n of list) {
            ids.add(n.id);
            if (n.children) walk(n.children);
        }
    }
    walk(nodes);
    return ids;
}

export const HierarchyFilter: React.FC<HierarchyFilterProps> = ({
    nodes,
    selected,
    onToggle,
    onExpand,
    onSearchChange,
    searchLoading = false,
    loadingNodeId,
    placeholder = 'Search...',
    loading = false,
}) => {
    const [search, setSearch] = useState('');
    const [expanded, setExpanded] = useState<Set<string>>(new Set());

    // Auto-expand top-level nodes when nodes change (initial load)
    useEffect(() => {
        if (nodes.length > 0 && !search) {
            setExpanded(new Set(nodes.map((n) => n.id)));
        }
    }, [nodes.length]);

    const handleSearchChange = (value: string) => {
        setSearch(value);
        if (onSearchChange) {
            onSearchChange(value);
        }
    };

    // Server-side search active: search text present + onSearchChange provided + not loading
    const isServerSearch = !!onSearchChange && !!search;

    // When onSearchChange is provided (server-side search), use nodes as-is;
    // otherwise filter locally (for small or fully-loaded trees)
    const filteredNodes = useMemo(() => {
        if (onSearchChange) return nodes;
        return search ? filterTree(nodes, search) : nodes;
    }, [nodes, search, onSearchChange]);

    const effectiveExpanded = useMemo(() => {
        // Local search: expand all matching branches
        if (search && !onSearchChange) return getAllIds(filteredNodes);
        // No search: use manual expansion state
        if (!search) return expanded;
        // Server search while loading: keep tree expanded (don't collapse prematurely)
        if (searchLoading) return expanded;
        // Server search results arrived: flat display (no nesting)
        return getAllIds(filteredNodes);
    }, [search, filteredNodes, expanded, onSearchChange, searchLoading]);

    const visibleNodes = useMemo(
        () => flattenVisible(filteredNodes, effectiveExpanded),
        [filteredNodes, effectiveExpanded]
    );

    const handleExpand = (node: TreeNode) => {
        // If node has children that haven't been loaded yet, trigger lazy load
        if (node.has_children && !node.childrenLoaded && onExpand) {
            onExpand(node.id, node.level);
        }
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(node.id)) {
                next.delete(node.id);
            } else {
                next.add(node.id);
            }
            return next;
        });
    };

    if (loading) {
        return (
            <div className="px-1 py-3 flex items-center justify-center gap-1.5">
                <span className="material-symbols-outlined text-[14px] text-text-sub animate-spin">
                    progress_activity
                </span>
                <span className="text-[10px] text-text-sub">Loading...</span>
            </div>
        );
    }

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
            <div className="max-h-[220px] overflow-y-auto">
                {searchLoading ? (
                    <div className="py-2 flex items-center justify-center gap-1.5">
                        <span className="material-symbols-outlined text-[14px] text-text-sub animate-spin">
                            progress_activity
                        </span>
                        <span className="text-[10px] text-text-sub">Searching...</span>
                    </div>
                ) : (
                    <>
                        {visibleNodes.length === 0 && search && (
                            <p className="text-[10px] text-text-sub py-2 px-1">No results</p>
                        )}
                        {visibleNodes.map((node) => {
                            const canExpand = (node.children && node.children.length > 0) || (!isServerSearch && node.has_children);
                            const isExpanded = effectiveExpanded.has(node.id);
                            const isChecked = selected.has(node.id);
                            const isLoading = loadingNodeId === node.id;
                            const searchLower = search.toLowerCase();
                            const isMatch = isServerSearch && (
                                node.id.toLowerCase().includes(searchLower) ||
                                node.label.toLowerCase().includes(searchLower)
                            );
                            const isAncestor = isServerSearch && !isMatch;

                            return (
                                <div
                                    key={node.id}
                                    className={`flex items-center gap-1 py-0.5 hover:bg-surface-light group ${isMatch ? 'bg-primary/5' : ''}`}
                                    style={{ paddingLeft: `${node.level * 12}px` }}
                                >
                                    {canExpand ? (
                                        <button
                                            onClick={() => handleExpand(node)}
                                            className="flex-shrink-0 w-4 h-4 flex items-center justify-center"
                                            disabled={isLoading}
                                        >
                                            {isLoading ? (
                                                <span className="material-symbols-outlined text-[12px] text-text-sub animate-spin">
                                                    progress_activity
                                                </span>
                                            ) : (
                                                <span
                                                    className={`material-symbols-outlined text-[12px] text-text-sub transition-transform duration-150 ${isExpanded ? 'rotate-90' : ''}`}
                                                >
                                                    chevron_right
                                                </span>
                                            )}
                                        </button>
                                    ) : (
                                        <span className="w-4 flex-shrink-0" />
                                    )}
                                    <label className="flex items-center gap-1.5 cursor-pointer flex-1 min-w-0">
                                        <input
                                            type="checkbox"
                                            checked={isChecked}
                                            onChange={() => onToggle(node.id)}
                                            className="w-3 h-3 rounded-sm border-border-light text-primary focus:ring-primary/20 focus:ring-1 flex-shrink-0 accent-primary"
                                        />
                                        {node.node_type && (
                                            <span
                                                className={`text-[8px] font-semibold px-1 py-px rounded border flex-shrink-0 leading-tight ${STATUS_COLORS[node.status || ''] || DEFAULT_STATUS_COLOR}`}
                                            >
                                                {TYPE_ABBREV[node.node_type] || node.node_type.slice(0, 3).toUpperCase()}
                                            </span>
                                        )}
                                        <span className={`text-[10px] font-mono flex-shrink-0 ${isMatch ? 'text-primary font-semibold' : 'text-text-sub/50'}`}>
                                            {node.id}
                                        </span>
                                        <span className={`text-xs truncate flex-1 min-w-0 ${isMatch ? 'text-primary font-medium' : isAncestor ? 'text-text-sub' : 'text-text-main'}`}>
                                            {node.label}
                                        </span>
                                    </label>
                                </div>
                            );
                        })}
                    </>
                )}
            </div>
        </div>
    );
};
