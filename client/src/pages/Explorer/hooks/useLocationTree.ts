import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../../../auth/useAuth';
import { TreeNode } from '../types';
import { fetchLocations, ApiTreeNode } from '../api/explorerApi';

function apiToTreeNode(api: ApiTreeNode, level: number): TreeNode {
    return {
        id: api.id,
        label: api.label,
        level,
        has_children: api.has_children,
        childrenLoaded: api.children.length > 0 || !api.has_children,
        children: api.children.map((c) => apiToTreeNode(c, level + 1)),
        node_type: api.node_type || undefined,
        status: api.status || undefined,
        path: api.path || undefined,
    };
}

function insertChildren(nodes: TreeNode[], parentId: string, children: ApiTreeNode[], parentLevel: number): TreeNode[] {
    return nodes.map((node) => {
        if (node.id === parentId) {
            return {
                ...node,
                childrenLoaded: true,
                children: children.map((c) => apiToTreeNode(c, parentLevel + 1)),
            };
        }
        if (node.children && node.children.length > 0) {
            return {
                ...node,
                children: insertChildren(node.children, parentId, children, parentLevel),
            };
        }
        return node;
    });
}

export function useLocationTree() {
    const { getApiAccessToken } = useAuth();
    const [treeNodes, setTreeNodes] = useState<TreeNode[]>([]);
    const [searchResults, setSearchResults] = useState<TreeNode[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [searchLoading, setSearchLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loadingNodeId, setLoadingNodeId] = useState<string | null>(null);
    const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Initial tree load
    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const token = await getApiAccessToken();
                if (!token || cancelled) return;
                const data = await fetchLocations(token);
                if (!cancelled) {
                    setTreeNodes(data.nodes.map((n) => apiToTreeNode(n, 0)));
                }
            } catch (err: any) {
                if (!cancelled) setError(err.message || 'Failed to load locations');
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        load();
        return () => { cancelled = true; };
    }, [getApiAccessToken]);

    // Server-side search (called from HierarchyFilter via onSearchChange)
    const handleSearch = useCallback((query: string) => {
        if (searchTimer.current) clearTimeout(searchTimer.current);

        if (!query) {
            setSearchResults(null);
            setSearchLoading(false);
            return;
        }
        setSearchLoading(true);
        searchTimer.current = setTimeout(async () => {
            try {
                const token = await getApiAccessToken();
                if (!token) return;
                const data = await fetchLocations(token, undefined, query);
                setSearchResults(data.nodes.map((n) => apiToTreeNode(n, 0)));
            } catch (err: any) {
                console.error('Location search failed:', err);
                setError(err.message || 'Search failed');
                setSearchResults(null); // Restore tree on error
            } finally {
                setSearchLoading(false);
            }
        }, 300);
    }, [getApiAccessToken]);

    const loadChildren = useCallback(async (parentId: string, parentLevel: number) => {
        setLoadingNodeId(parentId);
        try {
            const token = await getApiAccessToken();
            if (!token) return;
            const data = await fetchLocations(token, parentId);
            setTreeNodes((prev) => insertChildren(prev, parentId, data.nodes, parentLevel));
        } catch (err: any) {
            setError(err.message || 'Failed to load children');
        } finally {
            setLoadingNodeId(null);
        }
    }, [getApiAccessToken]);

    return {
        nodes: searchResults ?? treeNodes,
        loading,
        searchLoading,
        error,
        loadChildren,
        loadingNodeId,
        onSearchChange: handleSearch,
    };
}
