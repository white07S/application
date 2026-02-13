import React, { useState, useEffect } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import DevDataSidebar from './components/DevDataSidebar';
import TableViewer from './components/TableViewer';
import { useConnectionStatus } from './hooks/useConnectionStatus';
import { useQdrantStatus } from './hooks/useQdrantStatus';
import { useDataConsistency } from './hooks/useDataConsistency';
import { useTables } from './hooks/useTables';
import { useTableData } from './hooks/useTableData';
import { groupTablesByCategory, ViewMode, DataType } from './types';

const DevDataLayout: React.FC = () => {
    const { tableName } = useParams<{ tableName: string }>();
    const location = useLocation();
    const navigate = useNavigate();

    // Get view mode from URL params or default to overview
    const searchParams = new URLSearchParams(location.search);
    const urlViewMode = searchParams.get('view') as ViewMode;

    const [viewMode, setViewMode] = useState<ViewMode>(urlViewMode || 'overview');
    const [dataType, setDataType] = useState<DataType>('controls');

    // Update URL when view mode changes
    useEffect(() => {
        if (!tableName) {
            const params = new URLSearchParams(location.search);
            if (viewMode !== 'overview') {
                params.set('view', viewMode);
            } else {
                params.delete('view');
            }
            const newSearch = params.toString();
            const newUrl = newSearch ? `${location.pathname}?${newSearch}` : location.pathname;
            if (location.pathname + location.search !== newUrl) {
                navigate(newUrl, { replace: true });
            }
        }
    }, [viewMode, tableName, location, navigate]);

    const { status: connectionStatus, loading: connLoading, refresh: refreshConnection } = useConnectionStatus();
    const { status: qdrantStatus, loading: qdrantLoading, refresh: refreshQdrant } = useQdrantStatus();
    const { data: consistencyData, loading: consistencyLoading, refresh: refreshConsistency } = useDataConsistency();
    const { tables, loading: tablesLoading } = useTables();
    const {
        data: tableData,
        loading: dataLoading,
        page,
        pageSize,
        setPage,
        setPageSize,
        refresh: refreshData,
        expandRelationship,
    } = useTableData(tableName);

    // Render based on view mode
    const renderContent = () => {
        switch (viewMode) {
            case 'postgres':
                return renderPostgresView();
            case 'qdrant':
                return renderQdrantView();
            case 'consistency':
                return renderConsistencyView();
            case 'overview':
            default:
                return renderOverview();
        }
    };

    const renderOverview = () => {
        const grouped = groupTablesByCategory(tables);
        return (
            <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* PostgreSQL Summary */}
                    <div className="bg-white border border-border-light rounded shadow-card p-4">
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-sm font-medium text-text-main flex items-center gap-2">
                                <span className="material-symbols-outlined text-[16px] text-text-sub">dns</span>
                                PostgreSQL
                            </h3>
                            <div className={`w-2 h-2 rounded-full ${connectionStatus?.connected ? 'bg-green-500' : 'bg-red-500'}`} />
                        </div>
                        <div className="text-xs text-text-sub space-y-1">
                            <div>{tables.length} tables</div>
                            <div>{tables.reduce((sum, t) => sum + (t.record_count > 0 ? t.record_count : 0), 0).toLocaleString()} total records</div>
                        </div>
                    </div>

                    {/* Qdrant Summary */}
                    <div className="bg-white border border-border-light rounded shadow-card p-4">
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-sm font-medium text-text-main flex items-center gap-2">
                                <span className="material-symbols-outlined text-[16px] text-text-sub">hub</span>
                                Qdrant
                            </h3>
                            <div className={`w-2 h-2 rounded-full ${
                                qdrantStatus?.status === 'green' ? 'bg-green-500' :
                                qdrantStatus?.status === 'yellow' ? 'bg-yellow-500 animate-pulse' :
                                qdrantStatus?.status === 'red' ? 'bg-red-500' : 'bg-gray-400'
                            }`} />
                        </div>
                        <div className="text-xs text-text-sub space-y-1">
                            <div>{qdrantStatus?.points_count?.toLocaleString() || '0'} points</div>
                            <div>{qdrantStatus?.vectors_count?.toLocaleString() || '0'} vectors</div>
                        </div>
                    </div>
                </div>

                {/* Quick Consistency Check */}
                <div className="bg-white border border-border-light rounded shadow-card p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <span className="text-xs text-text-sub">Controls:</span>
                            <span className="text-sm font-mono">{consistencyData?.postgres_controls.toLocaleString() || '-'}</span>
                            <span className="text-xs text-text-sub">in PostgreSQL</span>
                            <span className="text-text-sub">vs</span>
                            <span className="text-sm font-mono">{consistencyData?.qdrant_points.toLocaleString() || '-'}</span>
                            <span className="text-xs text-text-sub">in Qdrant</span>
                        </div>
                        {consistencyData && (
                            <span className={`text-xs font-medium ${consistencyData.is_consistent ? 'text-green-600' : 'text-yellow-600'}`}>
                                {consistencyData.is_consistent ? '✓ Consistent' : `⚠ ${consistencyData.difference} difference`}
                            </span>
                        )}
                    </div>
                </div>
            </div>
        );
    };

    const renderPostgresView = () => {
        const grouped = groupTablesByCategory(tables);
        return (
            <div className="space-y-4">
                <div className="bg-white border border-border-light rounded shadow-card">
                    <div className="px-3 py-2 border-b border-border-light bg-surface-light/50">
                        <div className="flex items-center justify-between">
                            <h2 className="text-sm font-medium text-text-main">PostgreSQL Connection</h2>
                            <button
                                onClick={refreshConnection}
                                className="p-1 rounded hover:bg-surface-alt transition-colors"
                                disabled={connLoading}
                            >
                                <span className={`material-symbols-outlined text-[16px] text-text-sub ${connLoading ? 'animate-spin' : ''}`}>
                                    refresh
                                </span>
                            </button>
                        </div>
                    </div>
                    <div className="p-3">
                        {connectionStatus && (
                            <div className="grid grid-cols-3 gap-4">
                                <div>
                                    <div className="text-[10px] text-text-sub uppercase">Status</div>
                                    <div className="flex items-center gap-1.5 mt-1">
                                        <div className={`w-2 h-2 rounded-full ${connectionStatus.connected ? 'bg-green-500' : 'bg-red-500'}`} />
                                        <span className="text-xs">{connectionStatus.connected ? 'Connected' : 'Disconnected'}</span>
                                    </div>
                                </div>
                                <div>
                                    <div className="text-[10px] text-text-sub uppercase">Host</div>
                                    <div className="text-xs font-mono mt-1">{connectionStatus.url}</div>
                                </div>
                                <div>
                                    <div className="text-[10px] text-text-sub uppercase">Database</div>
                                    <div className="text-xs font-mono mt-1">{connectionStatus.database}</div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Tables by category */}
                <div className="space-y-3">
                    {grouped.map(category => (
                        <div key={category.id} className="bg-white border border-border-light rounded shadow-card p-3">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="material-symbols-outlined text-[14px] text-text-sub">{category.icon}</span>
                                <span className="text-xs font-medium text-text-main">{category.label}</span>
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-alt text-text-sub">
                                    {category.tables.length}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                                {category.tables.map(table => (
                                    <a
                                        key={table.name}
                                        href={`/devdata/${table.name}?view=${viewMode}`}
                                        className="flex items-center justify-between px-2 py-1.5 rounded border border-border-light hover:bg-surface-light text-xs"
                                    >
                                        <span className="truncate">{table.name}</span>
                                        <span className="text-[10px] text-text-sub">{table.record_count}</span>
                                    </a>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    };

    const renderQdrantView = () => {
        return (
            <div className="space-y-4">
                <div className="bg-white border border-border-light rounded shadow-card">
                    <div className="px-3 py-2 border-b border-border-light bg-surface-light/50">
                        <div className="flex items-center justify-between">
                            <h2 className="text-sm font-medium text-text-main">Qdrant Vector Database</h2>
                            <button
                                onClick={refreshQdrant}
                                className="p-1 rounded hover:bg-surface-alt transition-colors"
                                disabled={qdrantLoading}
                            >
                                <span className={`material-symbols-outlined text-[16px] text-text-sub ${qdrantLoading ? 'animate-spin' : ''}`}>
                                    refresh
                                </span>
                            </button>
                        </div>
                    </div>
                    <div className="p-4">
                        {qdrantStatus ? (
                            <div className="space-y-4">
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <div>
                                        <div className="text-[10px] text-text-sub uppercase">Status</div>
                                        <div className="flex items-center gap-1.5 mt-1">
                                            <div className={`w-2 h-2 rounded-full ${
                                                qdrantStatus.status === 'green' ? 'bg-green-500' :
                                                qdrantStatus.status === 'yellow' ? 'bg-yellow-500 animate-pulse' :
                                                qdrantStatus.status === 'red' ? 'bg-red-500' : 'bg-gray-400'
                                            }`} />
                                            <span className="text-xs capitalize">
                                                {qdrantStatus.status}
                                                {qdrantStatus.indexing_progress != null && ` (${qdrantStatus.indexing_progress}%)`}
                                            </span>
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] text-text-sub uppercase">Collection</div>
                                        <div className="text-xs font-mono mt-1">{qdrantStatus.collection_name}</div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] text-text-sub uppercase">Points</div>
                                        <div className="text-xs font-medium mt-1">{qdrantStatus.points_count?.toLocaleString()}</div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] text-text-sub uppercase">Vectors</div>
                                        <div className="text-xs font-medium mt-1">{qdrantStatus.vectors_count?.toLocaleString()}</div>
                                    </div>
                                </div>

                                {qdrantStatus.named_vectors && (
                                    <div>
                                        <div className="text-[10px] text-text-sub uppercase mb-2">Named Vectors</div>
                                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                                            {qdrantStatus.named_vectors.map(name => (
                                                <div key={name} className="px-2 py-1.5 rounded border border-border-light bg-surface-light">
                                                    <span className="text-xs font-mono">{name}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-xs text-text-sub">Qdrant not available</div>
                        )}
                    </div>
                </div>
            </div>
        );
    };

    const renderConsistencyView = () => {
        return (
            <div className="space-y-4">
                <div className="bg-white border border-border-light rounded shadow-card">
                    <div className="px-3 py-2 border-b border-border-light bg-surface-light/50">
                        <div className="flex items-center justify-between">
                            <h2 className="text-sm font-medium text-text-main">Data Consistency Check</h2>
                            <button
                                onClick={refreshConsistency}
                                className="p-1 rounded hover:bg-surface-alt transition-colors"
                                disabled={consistencyLoading}
                            >
                                <span className={`material-symbols-outlined text-[16px] text-text-sub ${consistencyLoading ? 'animate-spin' : ''}`}>
                                    refresh
                                </span>
                            </button>
                        </div>
                    </div>
                    <div className="p-4">
                        {consistencyData && (
                            <div className="space-y-4">
                                <div className="flex items-center justify-between p-4 bg-surface-light rounded">
                                    <div className="flex items-center gap-8">
                                        <div>
                                            <div className="text-[10px] text-text-sub uppercase">PostgreSQL Controls</div>
                                            <div className="text-2xl font-mono font-medium mt-1">
                                                {consistencyData.postgres_controls.toLocaleString()}
                                            </div>
                                        </div>
                                        <span className="text-text-sub text-lg">vs</span>
                                        <div>
                                            <div className="text-[10px] text-text-sub uppercase">Qdrant Points</div>
                                            <div className="text-2xl font-mono font-medium mt-1">
                                                {consistencyData.qdrant_points.toLocaleString()}
                                            </div>
                                        </div>
                                    </div>
                                    <div className={`px-3 py-2 rounded ${
                                        consistencyData.is_consistent
                                            ? 'bg-green-50 text-green-700'
                                            : 'bg-yellow-50 text-yellow-700'
                                    }`}>
                                        <span className="material-symbols-outlined text-[20px]">
                                            {consistencyData.is_consistent ? 'check_circle' : 'warning'}
                                        </span>
                                        <div className="text-xs font-medium mt-1">
                                            {consistencyData.is_consistent
                                                ? 'Consistent'
                                                : `${consistencyData.difference.toLocaleString()} difference`}
                                        </div>
                                    </div>
                                </div>

                                {!consistencyData.is_consistent && (
                                    <div className="p-3 bg-yellow-50 border border-yellow-200 rounded">
                                        <p className="text-xs text-yellow-800">
                                            ⚠️ Data inconsistency detected. {
                                                consistencyData.postgres_controls > consistencyData.qdrant_points
                                                    ? 'Some controls are missing from Qdrant. Re-run embedding generation.'
                                                    : 'Qdrant has more points than PostgreSQL controls. Consider re-syncing.'
                                            }
                                        </p>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    };

    if (tableName && tableData) {
        // Get the view mode from URL to know where to go back to
        const backView = searchParams.get('view') || 'overview';
        const backUrl = backView === 'overview' ? '/devdata' : `/devdata?view=${backView}`;

        return (
            <div className="max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4 py-4">
                {/* Header with back button */}
                <div className="flex items-center gap-3 mb-4">
                    <a
                        href={backUrl}
                        className="p-1.5 rounded hover:bg-surface-light transition-colors group"
                        title={`Back to ${backView}`}
                    >
                        <span className="material-symbols-outlined text-[18px] text-text-sub group-hover:text-text-main">
                            arrow_back
                        </span>
                    </a>
                    <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-[18px] text-text-sub">database</span>
                        <h1 className="text-base font-semibold text-text-main">Dev Data</h1>
                        <span className="text-text-sub">/</span>
                        <span className="text-sm font-mono text-text-main">{tableName}</span>
                    </div>
                    <div className="ml-auto flex items-center gap-2">
                        <span className="text-[10px] px-2 py-1 rounded bg-surface-alt text-text-sub">
                            {tableData.total.toLocaleString()} records
                        </span>
                        <button
                            onClick={refreshData}
                            className="p-1 rounded hover:bg-surface-light transition-colors"
                            disabled={dataLoading}
                            title="Refresh table data"
                        >
                            <span className={`material-symbols-outlined text-[16px] text-text-sub ${dataLoading ? 'animate-spin' : ''}`}>
                                refresh
                            </span>
                        </button>
                    </div>
                </div>

                <TableViewer
                    data={tableData}
                    loading={dataLoading}
                    page={page}
                    pageSize={pageSize}
                    onPageChange={setPage}
                    onPageSizeChange={setPageSize}
                    onRefresh={refreshData}
                    onExpandRelationship={expandRelationship}
                />
            </div>
        );
    }

    return (
        <div className="max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4 py-4">
            {/* Header with controls */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <h1 className="text-lg font-semibold text-text-main flex items-center gap-2">
                        <span className="material-symbols-outlined text-[20px] text-text-sub">database</span>
                        Dev Data
                    </h1>

                    {/* Data Type Dropdown */}
                    <select
                        value={dataType}
                        onChange={(e) => setDataType(e.target.value as DataType)}
                        className="text-xs px-2 py-1 border border-border-light rounded bg-white"
                    >
                        <option value="controls">Controls</option>
                        <option value="risks" disabled>Risks (Coming Soon)</option>
                        <option value="orgs" disabled>Organizations (Coming Soon)</option>
                    </select>
                </div>

                {/* View Mode Tabs */}
                <div className="flex items-center gap-1 p-0.5 bg-surface-light rounded border border-border-light">
                    {(['overview', 'postgres', 'qdrant', 'consistency'] as ViewMode[]).map(mode => (
                        <button
                            key={mode}
                            onClick={() => setViewMode(mode)}
                            className={`px-3 py-1 text-xs rounded transition-colors ${
                                viewMode === mode
                                    ? 'bg-white text-text-main font-medium shadow-sm'
                                    : 'text-text-sub hover:text-text-main'
                            }`}
                        >
                            {mode.charAt(0).toUpperCase() + mode.slice(1)}
                        </button>
                    ))}
                </div>
            </div>

            {/* Content based on view mode */}
            {renderContent()}
        </div>
    );
};

export default DevDataLayout;
