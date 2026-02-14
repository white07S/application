import React from 'react';
import { Circle, RefreshCw } from 'lucide-react';
import { CollectionSummaryResponse } from '../types';
import { formatNumber } from '../utils/formatters';

interface QdrantStatusBarProps {
  summary: CollectionSummaryResponse | null;
  loading: boolean;
  collectionName: string | null;
  onRefresh: () => void;
  lastRefresh: Date | null;
}

function statusColor(status: string | undefined): string {
  if (status === 'green' || status === 'ok' || status === 'enabled') {
    return 'text-green-600';
  }
  if (status === 'yellow') {
    return 'text-yellow-600';
  }
  if (status === 'red') {
    return 'text-red-600';
  }
  return 'text-gray-500';
}

const QdrantStatusBar: React.FC<QdrantStatusBarProps> = ({
  summary,
  loading,
  collectionName,
  onRefresh,
  lastRefresh,
}) => {
  return (
    <div className="flex flex-col gap-2 border-b border-border-light bg-white px-3 py-2">
      <div className="flex items-center gap-2">
        <div className="text-sm font-semibold text-text-main">Qdrant Browser</div>
        {collectionName && <div className="text-xs font-mono text-text-sub">/{collectionName}</div>}
        <div className="ml-auto flex items-center gap-2">
          <div className="text-[10px] text-text-sub">
            {lastRefresh ? `Refreshed ${lastRefresh.toLocaleTimeString()}` : 'Not refreshed yet'}
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs text-text-main hover:bg-surface-light disabled:opacity-40"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
        <div className="rounded border border-border-light bg-surface-light/70 px-2 py-1">
          <div className="text-[10px] uppercase text-text-sub">Status</div>
          <div className={`flex items-center gap-1 text-xs font-medium ${statusColor(summary?.status)}`}>
            <Circle size={10} fill="currentColor" />
            <span>{summary?.status || 'unknown'}</span>
          </div>
        </div>
        <div className="rounded border border-border-light bg-surface-light/70 px-2 py-1">
          <div className="text-[10px] uppercase text-text-sub">Points</div>
          <div className="text-xs font-medium text-text-main">{formatNumber(summary?.points_count)}</div>
        </div>
        <div className="rounded border border-border-light bg-surface-light/70 px-2 py-1">
          <div className="text-[10px] uppercase text-text-sub">Vectors</div>
          <div className="text-xs font-medium text-text-main">{formatNumber(summary?.vectors_count)}</div>
        </div>
        <div className="rounded border border-border-light bg-surface-light/70 px-2 py-1">
          <div className="text-[10px] uppercase text-text-sub">Aliases</div>
          <div className="text-xs font-medium text-text-main">{formatNumber(summary?.aliases_count)}</div>
        </div>
        <div className="rounded border border-border-light bg-surface-light/70 px-2 py-1">
          <div className="text-[10px] uppercase text-text-sub">Snapshots</div>
          <div className="text-xs font-medium text-text-main">{formatNumber(summary?.snapshots_count)}</div>
        </div>
        <div className="rounded border border-border-light bg-surface-light/70 px-2 py-1">
          <div className="text-[10px] uppercase text-text-sub">Named Vectors</div>
          <div className="truncate text-xs font-mono text-text-main">
            {summary?.vectors?.length ? summary.vectors.join(', ') : 'default'}
          </div>
        </div>
      </div>
    </div>
  );
};

export default QdrantStatusBar;

