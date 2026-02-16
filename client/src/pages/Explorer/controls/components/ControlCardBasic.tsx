import React from 'react';
import { Control, ControlRelationships } from '../types';

interface Props {
    control: Control;
    relationships: ControlRelationships;
}

const statusStyle: Record<string, string> = {
    Active: 'bg-green-50 text-green-700 border-green-100',
    Inactive: 'bg-red-50 text-red-700 border-red-100',
    'Under Review': 'bg-amber-50 text-amber-700 border-amber-100',
};

export const ControlCardBasic: React.FC<Props> = ({ control, relationships }) => {
    return (
        <div className="flex flex-col gap-1.5 p-3 min-w-0">
            {/* Top row: ID + status */}
            <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs bg-surface-light text-text-sub px-1.5 py-0.5 rounded-sm">
                    {control.control_id}
                </span>
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-sm border ${statusStyle[control.control_status] || 'bg-gray-50 text-gray-600 border-gray-100'}`}>
                    {control.control_status}
                </span>
            </div>

            {/* Title */}
            <h4 className="text-sm font-medium text-text-main leading-tight line-clamp-2">
                {control.control_title}
            </h4>

            {/* Description */}
            <p className="text-xs text-text-sub leading-relaxed line-clamp-2">
                {control.control_description}
            </p>

            {/* Badges row */}
            <div className="flex flex-wrap items-center gap-1 mt-0.5">
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-sm border ${control.hierarchy_level === 'L1' ? 'bg-blue-50 text-blue-700 border-blue-100' : 'bg-purple-50 text-purple-700 border-purple-100'}`}>
                    {control.hierarchy_level}
                </span>
                {control.key_control && (
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-sm border bg-amber-50 text-amber-700 border-amber-100">
                        Key
                    </span>
                )}
                <span className="text-[10px] text-text-sub px-1.5 py-0.5 rounded-sm border border-border-light bg-white">
                    {control.preventative_detective}
                </span>
                <span className="text-[10px] text-text-sub px-1.5 py-0.5 rounded-sm border border-border-light bg-white">
                    {control.manual_automated}
                </span>
            </div>

            {/* Owner */}
            <div className="flex items-center gap-1 min-w-0">
                <span className="material-symbols-outlined text-[12px] text-text-sub flex-shrink-0">person</span>
                <span className="text-xs text-text-main truncate">{control.control_owner}</span>
            </div>

            {/* Risk themes */}
            {relationships.risk_themes.length > 0 && (
                <div className="flex items-center gap-1 min-w-0">
                    <span className="material-symbols-outlined text-[12px] text-text-sub flex-shrink-0">category</span>
                    <span className="text-xs text-text-main truncate" title={relationships.risk_themes.map((t) => t.name).join(', ')}>
                        {relationships.risk_themes.map((t) => t.name).join(', ')}
                    </span>
                </div>
            )}

            {/* Parent (L2) or Children (L1) */}
            {control.hierarchy_level === 'L2' && relationships.parent_control_id && (
                <div className="flex items-center gap-1 min-w-0">
                    <span className="material-symbols-outlined text-[12px] text-text-sub flex-shrink-0">family_link</span>
                    <span className="text-[10px] text-text-sub">Parent:</span>
                    <span className="font-mono text-[10px] bg-surface-light text-text-main px-1 py-0.5 rounded-sm">
                        {relationships.parent_control_id}
                    </span>
                </div>
            )}
            {control.hierarchy_level === 'L1' && relationships.child_control_ids.length > 0 && (
                <div className="flex items-center gap-1 min-w-0 flex-wrap">
                    <span className="material-symbols-outlined text-[12px] text-text-sub flex-shrink-0">family_link</span>
                    <span className="text-[10px] text-text-sub">Children:</span>
                    {relationships.child_control_ids.map((id) => (
                        <span key={id} className="font-mono text-[10px] bg-surface-light text-text-main px-1 py-0.5 rounded-sm">
                            {id}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
};
