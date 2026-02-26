import React from 'react';

interface KPICardProps {
    label: string;
    value: string | number;
    icon: string;
    subtitle?: string;
    color?: string;
}

const KPICard: React.FC<KPICardProps> = ({ label, value, icon, subtitle, color = 'text-text-main' }) => (
    <div className="bg-white border border-border-light rounded-lg p-3 flex items-center gap-3">
        <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-surface-light flex items-center justify-center">
            <span className="material-symbols-outlined text-[18px] text-text-sub">{icon}</span>
        </div>
        <div className="min-w-0">
            <div className={`text-lg font-semibold leading-tight ${color}`}>
                {typeof value === 'number' ? value.toLocaleString() : value}
            </div>
            <div className="text-[10px] text-text-sub leading-tight">{label}</div>
            {subtitle && <div className="text-[9px] text-text-sub/60 leading-tight mt-0.5">{subtitle}</div>}
        </div>
    </div>
);

export default KPICard;
