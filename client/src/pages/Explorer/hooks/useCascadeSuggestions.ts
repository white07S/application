import { useMemo, useState, useCallback } from 'react';
import { FilterState, FlatItem, TreeNode } from '../types';

export interface CascadeSuggestion {
    /** Which section triggered this suggestion */
    sourceSection: string;
    /** Which section is being suggested */
    targetSection: 'selectedAUs' | 'selectedCEs' | 'selectedLocations';
    /** The IDs to suggest selecting */
    suggestedIds: string[];
    /** Human-readable message */
    message: string;
}

/**
 * Extract all node IDs from a tree (recursively).
 */
function collectTreeIds(nodes: TreeNode[]): Set<string> {
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

/**
 * Extract the source ID portion from a composite node_id.
 * e.g., "function:8156" → "8156", "location:B663" → "B663"
 */
function sourceId(nodeId: string): string {
    const idx = nodeId.indexOf(':');
    return idx >= 0 ? nodeId.slice(idx + 1) : nodeId;
}

/**
 * Compute cascade suggestions based on current selections and data.
 *
 * Relationships:
 *   - Function → AUs (via AU.function_node_id)
 *   - Location/CE → AUs (via AU.location_node_id)
 *   - Location (company) ↔ CE (via matching source IDs)
 */
export function useCascadeSuggestions(
    state: FilterState,
    aus: FlatItem[],
    ceItems: FlatItem[],
    locationNodes: TreeNode[],
) {
    // Track which suggestions the user has dismissed (keyed by a stable string)
    const [dismissed, setDismissed] = useState<Set<string>>(new Set());

    const suggestions = useMemo(() => {
        if (!state.cascadeEnabled) return [];

        const result: CascadeSuggestion[] = [];
        const selectedAUIds = state.selectedAUs;

        // --- Functions → AUs ---
        if (state.selectedFunctions.size > 0) {
            const linkedAUs = aus.filter(
                (au) =>
                    au.function_node_id &&
                    state.selectedFunctions.has(au.function_node_id) &&
                    !selectedAUIds.has(au.id)
            );
            if (linkedAUs.length > 0) {
                result.push({
                    sourceSection: 'Functions',
                    targetSection: 'selectedAUs',
                    suggestedIds: linkedAUs.map((a) => a.id),
                    message: `${linkedAUs.length} assessment unit${linkedAUs.length > 1 ? 's' : ''} linked to selected functions`,
                });
            }
        }

        // --- Locations → AUs ---
        if (state.selectedLocations.size > 0) {
            const linkedAUs = aus.filter(
                (au) =>
                    au.location_node_id &&
                    au.location_type === 'location' &&
                    state.selectedLocations.has(au.location_node_id) &&
                    !selectedAUIds.has(au.id)
            );
            if (linkedAUs.length > 0) {
                result.push({
                    sourceSection: 'Locations',
                    targetSection: 'selectedAUs',
                    suggestedIds: linkedAUs.map((a) => a.id),
                    message: `${linkedAUs.length} assessment unit${linkedAUs.length > 1 ? 's' : ''} linked to selected locations`,
                });
            }
        }

        // --- CEs → AUs ---
        if (state.selectedCEs.size > 0) {
            const linkedAUs = aus.filter(
                (au) =>
                    au.location_node_id &&
                    au.location_type === 'consolidated' &&
                    state.selectedCEs.has(au.location_node_id) &&
                    !selectedAUIds.has(au.id)
            );
            if (linkedAUs.length > 0) {
                result.push({
                    sourceSection: 'Consolidated Entities',
                    targetSection: 'selectedAUs',
                    suggestedIds: linkedAUs.map((a) => a.id),
                    message: `${linkedAUs.length} assessment unit${linkedAUs.length > 1 ? 's' : ''} linked to selected entities`,
                });
            }
        }

        // --- Location companies → CEs (matching source IDs) ---
        if (state.selectedLocations.size > 0 && ceItems.length > 0) {
            // Build a set of source IDs from selected location nodes
            const selectedLocSourceIds = new Set<string>();
            state.selectedLocations.forEach((id) => selectedLocSourceIds.add(sourceId(id)));

            const matchingCEs = ceItems.filter(
                (ce) =>
                    selectedLocSourceIds.has(sourceId(ce.id)) &&
                    !state.selectedCEs.has(ce.id)
            );
            if (matchingCEs.length > 0) {
                result.push({
                    sourceSection: 'Locations',
                    targetSection: 'selectedCEs',
                    suggestedIds: matchingCEs.map((c) => c.id),
                    message: `${matchingCEs.length} consolidated entit${matchingCEs.length > 1 ? 'ies' : 'y'} match selected locations`,
                });
            }
        }

        // --- CEs → Location companies (matching source IDs) ---
        if (state.selectedCEs.size > 0) {
            const selectedCESourceIds = new Set<string>();
            state.selectedCEs.forEach((id) => selectedCESourceIds.add(sourceId(id)));

            // Find matching location nodes from loaded tree data
            const allLocationIds = collectTreeIds(locationNodes);
            const matchingLocIds: string[] = [];
            allLocationIds.forEach((locId) => {
                if (
                    selectedCESourceIds.has(sourceId(locId)) &&
                    !state.selectedLocations.has(locId)
                ) {
                    matchingLocIds.push(locId);
                }
            });
            if (matchingLocIds.length > 0) {
                result.push({
                    sourceSection: 'Consolidated Entities',
                    targetSection: 'selectedLocations',
                    suggestedIds: matchingLocIds,
                    message: `${matchingLocIds.length} location${matchingLocIds.length > 1 ? 's' : ''} match selected entities`,
                });
            }
        }

        // Filter out dismissed suggestions
        return result.filter((s) => {
            const key = `${s.sourceSection}→${s.targetSection}`;
            return !dismissed.has(key);
        });
    }, [state, aus, ceItems, locationNodes, dismissed]);

    const dismiss = useCallback((suggestion: CascadeSuggestion) => {
        const key = `${suggestion.sourceSection}→${suggestion.targetSection}`;
        setDismissed((prev) => new Set(prev).add(key));
    }, []);

    // Reset dismissed when selections change significantly
    const resetDismissed = useCallback(() => {
        setDismissed(new Set());
    }, []);

    return { suggestions, dismiss, resetDismissed };
}
