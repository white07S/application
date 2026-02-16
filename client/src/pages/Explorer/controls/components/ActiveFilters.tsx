import React from 'react';

interface Props {
    filterKeyControl: boolean;
    filterActiveOnly: boolean;
    onToggleKeyControl: () => void;
    onToggleActiveOnly: () => void;
    totalFiltered: number;
    totalAll: number;
}

export const ActiveFilters: React.FC<Props> = ({
    filterKeyControl,
    filterActiveOnly,
    onToggleKeyControl,
    onToggleActiveOnly,
    totalFiltered,
    totalAll,
}) => {
    const chipBase = 'text-[10px] font-medium px-2 py-1 rounded-sm border transition-colors cursor-pointer select-none';
    const chipOn = 'bg-primary/10 text-primary border-primary/20';
    const chipOff = 'bg-white text-text-sub border-border-light hover:border-border-dark';

    return (
        <div className="flex items-center gap-2 py-2">
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
            <span className="text-xs text-text-sub ml-auto">
                Showing <strong className="text-text-main">{totalFiltered}</strong> of {totalAll} controls
            </span>
        </div>
    );
};
