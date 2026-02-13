import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { TableInfo, ConnectionStatus, groupTablesByCategory } from '../types';

interface DevDataSidebarProps {
    tables: TableInfo[];
    connectionStatus: ConnectionStatus | null;
    loading: boolean;
}

const DevDataSidebar: React.FC<DevDataSidebarProps> = ({ tables, connectionStatus, loading }) => {
    const { tableName: activeTable } = useParams<{ tableName: string }>();
    const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

    const categories = groupTablesByCategory(tables);

    const toggleCategory = (catId: string) => {
        setCollapsed(prev => ({ ...prev, [catId]: !prev[catId] }));
    };

    const formatTableName = (name: string) => {
        // Strip common prefixes for readability, but keep enough for context
        // Remove leading layer_domain_ prefix (e.g., "src_controls_", "ai_controls_")
        const stripped = name.replace(/^[a-z]+_[a-z]+_(ref_|rel_has_|rel_|model_|main|versions)/, (match) => {
            // Keep the kind prefix for clarity in short names
            return '';
        });
        return stripped || name;
    };

    return (
        <aside className="w-full border-r border-border-light overflow-y-auto h-[calc(100vh-48px)] sticky top-12 py-3">
            {/* Connection Status */}
            <div className="px-3 mb-3">
                <div className="flex items-center gap-2 px-2 py-1.5 rounded bg-surface-alt">
                    <div className={`w-2 h-2 rounded-full ${connectionStatus?.connected ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span className="text-xs font-medium text-text-main">
                        {connectionStatus?.connected ? 'Connected' : 'Disconnected'}
                    </span>
                    {loading && (
                        <span className="material-symbols-outlined text-[14px] text-text-sub animate-spin ml-auto">refresh</span>
                    )}
                </div>
                {connectionStatus && (
                    <div className="mt-1 px-2 text-[10px] text-text-sub space-y-0.5">
                        <div className="truncate" title={connectionStatus.url}>{connectionStatus.database}</div>
                    </div>
                )}
            </div>

            {/* Divider */}
            <div className="border-t border-border-light mx-3 mb-2" />

            {/* Table Categories - dynamically rendered */}
            <nav className="px-2 space-y-0.5">
                {categories.map(category => (
                    <div key={category.id}>
                        <button
                            onClick={() => toggleCategory(category.id)}
                            className="w-full flex items-center gap-2 px-2 py-1.5 text-xs font-medium text-text-sub hover:text-text-main hover:bg-surface-light rounded transition-colors"
                        >
                            <span className="material-symbols-outlined text-[16px]">{category.icon}</span>
                            <span className="flex-1 text-left">{category.label}</span>
                            <span className="text-[10px] text-text-sub bg-surface-alt px-1.5 py-0.5 rounded">
                                {category.tables.length}
                            </span>
                            <span className="material-symbols-outlined text-[14px] text-text-sub">
                                {collapsed[category.id] ? 'expand_more' : 'expand_less'}
                            </span>
                        </button>

                        {!collapsed[category.id] && (
                            <div className="ml-2 space-y-0.5">
                                {category.tables.map(table => {
                                    const isActive = activeTable === table.name;
                                    return (
                                        <Link
                                            key={table.name}
                                            to={`/devdata/${table.name}`}
                                            className={`flex items-center justify-between gap-2 px-3 py-1.5 text-xs rounded transition-colors ${isActive
                                                ? 'bg-red-50 text-primary font-medium'
                                                : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                                                }`}
                                            title={table.name}
                                        >
                                            <span className="truncate">{formatTableName(table.name)}</span>
                                            <span className={`text-[10px] shrink-0 px-1.5 py-0.5 rounded ${isActive
                                                ? 'bg-red-100 text-primary'
                                                : 'bg-surface-alt text-text-sub'
                                                }`}>
                                                {table.record_count >= 0 ? table.record_count : '?'}
                                            </span>
                                        </Link>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                ))}
            </nav>
        </aside>
    );
};

export default DevDataSidebar;
