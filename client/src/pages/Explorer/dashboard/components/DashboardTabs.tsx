import React from 'react';
import type { DashboardTab } from '../types';

interface DashboardTabsProps {
    activeTab: DashboardTab;
    onTabChange: (tab: DashboardTab) => void;
}

const TABS: { key: DashboardTab; label: string; icon: string }[] = [
    { key: 'overview', label: 'Executive Overview', icon: 'dashboard' },
    { key: 'doc-quality', label: 'Doc Quality', icon: 'checklist' },
    { key: 'controls', label: 'Control Explorer', icon: 'search' },
    { key: 'history', label: 'History & Trends', icon: 'trending_up' },
    { key: 'analytics', label: 'Portfolio Analytics', icon: 'analytics' },
    { key: 'regulatory', label: 'Regulatory', icon: 'gavel' },
];

const DashboardTabs: React.FC<DashboardTabsProps> = ({ activeTab, onTabChange }) => (
    <div className="flex gap-0.5 border-b border-border-light mb-3 overflow-x-auto">
        {TABS.map(tab => (
            <button
                key={tab.key}
                onClick={() => onTabChange(tab.key)}
                className={`flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium border-b-2 transition-colors whitespace-nowrap
                    ${activeTab === tab.key
                        ? 'border-primary text-primary'
                        : 'border-transparent text-text-sub hover:text-text-main hover:bg-surface-light'
                    }`}
            >
                <span className="material-symbols-outlined text-[14px]">{tab.icon}</span>
                {tab.label}
            </button>
        ))}
    </div>
);

export default DashboardTabs;
