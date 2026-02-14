import React from 'react';

interface ChipData {
    id: string;
    label: string;
    section: string;
}

interface FilterChipsProps {
    chips: ChipData[];
    onRemove: (chip: ChipData) => void;
    maxVisible?: number;
}

export const FilterChips: React.FC<FilterChipsProps> = ({
    chips,
    onRemove,
    maxVisible = 6,
}) => {
    if (chips.length === 0) return null;

    const visible = chips.slice(0, maxVisible);
    const overflow = chips.length - maxVisible;

    return (
        <div className="flex flex-wrap gap-1 py-1.5">
            {visible.map((chip) => (
                <span
                    key={`${chip.section}-${chip.id}`}
                    className="inline-flex items-center gap-0.5 bg-surface-light text-xs text-text-main px-2 py-0.5 rounded-sm border border-border-light"
                >
                    <span className="truncate max-w-[120px]">{chip.label}</span>
                    <button
                        onClick={() => onRemove(chip)}
                        className="text-text-sub hover:text-primary flex-shrink-0 ml-0.5"
                    >
                        <span className="material-symbols-outlined text-[10px]">close</span>
                    </button>
                </span>
            ))}
            {overflow > 0 && (
                <span className="text-[10px] text-text-sub py-0.5 px-1">
                    +{overflow} more
                </span>
            )}
        </div>
    );
};
