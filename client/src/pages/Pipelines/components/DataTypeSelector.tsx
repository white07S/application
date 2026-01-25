import React from 'react';
import { DataType, VALIDATION_RULES } from '../types';

interface DataTypeSelectorProps {
    value: DataType;
    onChange: (type: DataType) => void;
    disabled?: boolean;
}

const dataTypes: { value: DataType; label: string; icon: string; description: string }[] = [
    {
        value: 'issues',
        label: 'Issues',
        icon: 'report_problem',
        description: '4 xlsx files required, min 5KB each',
    },
    {
        value: 'controls',
        label: 'Controls',
        icon: 'verified_user',
        description: '1 xlsx file required, min 5KB',
    },
    {
        value: 'actions',
        label: 'Actions',
        icon: 'task_alt',
        description: '1 xlsx file required, min 5KB',
    },
];

const DataTypeSelector: React.FC<DataTypeSelectorProps> = ({ value, onChange, disabled }) => {
    const selectedType = dataTypes.find(t => t.value === value);
    const rules = VALIDATION_RULES[value];

    return (
        <div className="space-y-2">
            <label className="block text-[10px] font-bold text-text-sub uppercase tracking-wider">
                Data Type
            </label>
            <div className="flex items-start gap-4">
                <div className="relative flex-1 max-w-xs">
                    <select
                        value={value}
                        onChange={(e) => onChange(e.target.value as DataType)}
                        disabled={disabled}
                        className="w-full text-sm font-medium bg-white border border-border-light rounded px-3 py-2.5 pr-10 focus:ring-1 focus:ring-primary focus:border-primary text-text-main cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{
                            WebkitAppearance: 'none',
                            MozAppearance: 'none',
                            appearance: 'none',
                            backgroundImage: 'none',
                        }}
                    >
                        {dataTypes.map((type) => (
                            <option key={type.value} value={type.value}>
                                {type.label}
                            </option>
                        ))}
                    </select>
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-text-sub">
                        <span className="material-symbols-outlined text-[18px]">expand_more</span>
                    </span>
                </div>
                {selectedType && (
                    <div className="flex items-center gap-3 px-4 py-2.5 bg-surface-light rounded border border-border-light">
                        <span className={`material-symbols-outlined text-[18px] ${
                            value === 'issues' ? 'text-amber-600' :
                            value === 'controls' ? 'text-blue-600' : 'text-green-600'
                        }`}>
                            {selectedType.icon}
                        </span>
                        <div className="text-xs text-text-sub">
                            <span className="font-medium text-text-main">{rules.fileCount} file{rules.fileCount > 1 ? 's' : ''}</span>
                            {' '}required, min {rules.minSizeKb}KB each
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default DataTypeSelector;
