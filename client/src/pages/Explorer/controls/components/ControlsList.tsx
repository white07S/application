import React from 'react';
import { ControlGroup } from '../types';
import { ControlCard } from './ControlCard';
import { GroupHeader } from './GroupHeader';

interface Props {
    groups: ControlGroup[];
    expandedGroups: Set<string>;
    onToggleGroup: (key: string) => void;
    isGrouped: boolean;
}

export const ControlsList: React.FC<Props> = ({ groups, expandedGroups, onToggleGroup, isGrouped }) => {
    const totalControls = groups.reduce((sum, g) => sum + g.controls.length, 0);

    if (totalControls === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-16 text-text-sub">
                <span className="material-symbols-outlined text-[32px] mb-2">search_off</span>
                <span className="text-sm font-medium">No controls match your current filters</span>
                <span className="text-xs mt-1">Try adjusting your search or filter criteria</span>
            </div>
        );
    }

    // When expandedGroups is empty, treat all groups as expanded (initial state)
    const isExpanded = (key: string) => expandedGroups.size === 0 || expandedGroups.has(key);

    if (!isGrouped) {
        // Flat list — single group, no header
        return (
            <div className="space-y-2">
                {groups[0]?.controls.map((item) => (
                    <ControlCard key={item.control.control_id} item={item} />
                ))}
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {groups.map((group) => (
                <div key={group.key}>
                    <GroupHeader
                        label={group.label}
                        count={group.controls.length}
                        expanded={isExpanded(group.key)}
                        onToggle={() => onToggleGroup(group.key)}
                    />
                    {isExpanded(group.key) && (
                        <div className="space-y-2 mt-2">
                            {group.controls.map((item) => (
                                <ControlCard key={item.control.control_id} item={item} />
                            ))}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
};
