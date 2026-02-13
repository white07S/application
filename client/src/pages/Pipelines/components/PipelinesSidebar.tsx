import React from 'react';
import { useLocation, Link } from 'react-router-dom';

interface SidebarItem {
    id: string;
    label: string;
    icon: string;
    path?: string;
    disabled?: boolean;
}

interface SidebarSection {
    title: string;
    items: SidebarItem[];
}

const sidebarSections: SidebarSection[] = [
    {
        title: 'Categories',
        items: [
            { id: 'upload', label: 'Data Upload', icon: 'cloud_upload', path: '/pipelines/upload' },
            { id: 'ingestion', label: 'Ingestion', icon: 'input', path: '/pipelines/ingestion' },
            { id: 'exports', label: 'Exports', icon: 'output', disabled: true },
            { id: 'archival', label: 'Archival', icon: 'archive', disabled: true },
        ],
    },
    {
        title: 'Monitoring',
        items: [
            { id: 'metrics', label: 'Metrics', icon: 'analytics', disabled: true },
            { id: 'logs', label: 'Logs', icon: 'history', disabled: true },
        ],
    },
];

const PipelinesSidebar: React.FC = () => {
    const location = useLocation();

    return (
        <aside className="w-56 shrink-0 pr-4 border-r border-border-light min-h-[calc(100vh-8rem)]">
            <nav className="flex flex-col gap-6">
                {sidebarSections.map((section, sectionIndex) => (
                    <div key={section.title} className={`flex flex-col ${sectionIndex > 0 ? 'pt-4 border-t border-border-light' : ''}`}>
                        <h3 className="px-3 text-[10px] font-bold text-text-sub uppercase tracking-wider mb-3">
                            {section.title}
                        </h3>
                        <div className="flex flex-col gap-0.5">
                            {section.items.map((item) => {
                                const isActive = item.path && location.pathname === item.path;
                                const isDisabled = item.disabled;

                                if (isDisabled) {
                                    return (
                                        <div
                                            key={item.id}
                                            className="flex items-center gap-3 px-3 py-2 text-xs font-medium text-text-sub/40 rounded cursor-not-allowed"
                                        >
                                            <span className="material-symbols-outlined text-[18px]">{item.icon}</span>
                                            {item.label}
                                        </div>
                                    );
                                }

                                return (
                                    <Link
                                        key={item.id}
                                        to={item.path || '#'}
                                        className={`flex items-center gap-3 px-3 py-2 text-xs font-medium rounded transition-all ${
                                            isActive
                                                ? 'bg-red-50 text-primary'
                                                : 'text-text-sub hover:text-text-main hover:bg-surface-hover'
                                        }`}
                                    >
                                        <span className={`material-symbols-outlined text-[18px] ${isActive ? 'text-primary' : ''}`}>
                                            {item.icon}
                                        </span>
                                        {item.label}
                                    </Link>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </nav>
        </aside>
    );
};

export default PipelinesSidebar;
