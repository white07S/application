import React from 'react';

interface SummaryCardProps {
    title: string;
    icon?: string;
    children: React.ReactNode;
    className?: string;
}

const SummaryCard: React.FC<SummaryCardProps> = ({ title, icon, children, className = '' }) => (
    <div className={`bg-white border border-border-light rounded-lg ${className}`}>
        <div className="px-3 py-2 border-b border-border-light flex items-center gap-1.5">
            {icon && <span className="material-symbols-outlined text-[14px] text-text-sub">{icon}</span>}
            <h3 className="text-xs font-medium text-text-main">{title}</h3>
        </div>
        <div className="p-3">{children}</div>
    </div>
);

export default SummaryCard;
