import React from 'react';

interface DateFilterProps {
    value: string;
    onChange: (date: string) => void;
}

export const DateFilter: React.FC<DateFilterProps> = ({ value, onChange }) => {
    return (
        <div className="px-1">
            <input
                type="date"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-full px-2 py-1.5 text-xs border border-border-light bg-white text-text-main focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 rounded-sm"
            />
        </div>
    );
};
