import React from 'react';

interface Props {
    filterKeyControl: boolean;
    filterActiveOnly: boolean;
    filterLevel1: boolean;
    filterLevel2: boolean;
    onToggleKeyControl: () => void;
    onToggleActiveOnly: () => void;
    onToggleLevel1: () => void;
    onToggleLevel2: () => void;
    totalFiltered: number;
    totalAll: number;
    filterLogic?: 'and' | 'or';
    relationshipScope?: 'owns' | 'related' | 'both';
    onFilterLogicChange?: (logic: 'and' | 'or') => void;
    onRelationshipScopeChange?: (scope: 'owns' | 'related' | 'both') => void;
}

export const ActiveFilters: React.FC<Props> = ({
    filterKeyControl,
    filterActiveOnly,
    filterLevel1,
    filterLevel2,
    onToggleKeyControl,
    onToggleActiveOnly,
    onToggleLevel1,
    onToggleLevel2,
    totalFiltered,
    totalAll,
    filterLogic = 'and',
    relationshipScope = 'both',
    onFilterLogicChange,
    onRelationshipScopeChange,
}) => {
    const chipBase = 'text-[10px] font-medium px-2 py-1 rounded-sm border transition-colors cursor-pointer select-none';
    const chipOn = 'bg-primary/10 text-primary border-primary/20';
    const chipOff = 'bg-white text-text-sub border-border-light hover:border-border-dark';

    const segmentBase = 'text-[10px] font-medium px-1.5 py-0.5 border transition-colors cursor-pointer select-none';
    const segmentOn = 'bg-primary text-white border-primary';
    const segmentOff = 'bg-white text-text-sub border-border-light hover:border-border-dark';

    return (
        <div className="flex flex-wrap items-center gap-2 py-2">
            <button
                onClick={onToggleKeyControl}
                className={`${chipBase} ${filterKeyControl ? chipOn : chipOff}`}
            >
                <span className="material-symbols-outlined text-[10px] align-middle mr-0.5">
                    {filterKeyControl ? 'check' : 'close'}
                </span>
                Key Controls
            </button>
            <button
                onClick={onToggleActiveOnly}
                className={`${chipBase} ${filterActiveOnly ? chipOn : chipOff}`}
            >
                <span className="material-symbols-outlined text-[10px] align-middle mr-0.5">
                    {filterActiveOnly ? 'check' : 'close'}
                </span>
                Active Only
            </button>
            <button
                onClick={onToggleLevel1}
                className={`${chipBase} ${filterLevel1 ? chipOn : chipOff}`}
            >
                <span className="material-symbols-outlined text-[10px] align-middle mr-0.5">
                    {filterLevel1 ? 'check' : 'close'}
                </span>
                Level 1
            </button>
            <button
                onClick={onToggleLevel2}
                className={`${chipBase} ${filterLevel2 ? chipOn : chipOff}`}
            >
                <span className="material-symbols-outlined text-[10px] align-middle mr-0.5">
                    {filterLevel2 ? 'check' : 'close'}
                </span>
                Level 2
            </button>

            {/* Separator */}
            <div className="w-px h-4 bg-border-light mx-1" />

            {/* Filter logic: AND / OR */}
            {onFilterLogicChange && (
                <div className="flex items-center rounded-sm overflow-hidden">
                    <button
                        onClick={() => onFilterLogicChange('and')}
                        className={`${segmentBase} rounded-l-sm ${filterLogic === 'and' ? segmentOn : segmentOff}`}
                    >
                        AND
                    </button>
                    <button
                        onClick={() => onFilterLogicChange('or')}
                        className={`${segmentBase} rounded-r-sm border-l-0 ${filterLogic === 'or' ? segmentOn : segmentOff}`}
                    >
                        OR
                    </button>
                </div>
            )}

            {/* Relationship scope */}
            {onRelationshipScopeChange && (
                <div className="flex items-center rounded-sm overflow-hidden">
                    <button
                        onClick={() => onRelationshipScopeChange('owns')}
                        className={`${segmentBase} rounded-l-sm ${relationshipScope === 'owns' ? segmentOn : segmentOff}`}
                        title="Only owning relationships"
                    >
                        Owns
                    </button>
                    <button
                        onClick={() => onRelationshipScopeChange('both')}
                        className={`${segmentBase} border-l-0 ${relationshipScope === 'both' ? segmentOn : segmentOff}`}
                        title="Both owning and related"
                    >
                        Both
                    </button>
                    <button
                        onClick={() => onRelationshipScopeChange('related')}
                        className={`${segmentBase} rounded-r-sm border-l-0 ${relationshipScope === 'related' ? segmentOn : segmentOff}`}
                        title="Only related relationships"
                    >
                        Related
                    </button>
                </div>
            )}

            <span className="text-xs text-text-sub ml-auto">
                Showing <strong className="text-text-main">{totalFiltered}</strong> of {totalAll} controls
            </span>
        </div>
    );
};
