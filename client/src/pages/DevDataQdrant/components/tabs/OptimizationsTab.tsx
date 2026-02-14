import React, { useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { qdrantBrowserApi } from '../../api/qdrantBrowserApi';
import { OptimizationsResponse } from '../../types';
import EmptyState from '../EmptyState';
import ErrorState from '../ErrorState';

type SegmentStatus = 'idle' | 'queued' | 'running';

interface SegmentSquare {
  status: SegmentStatus;
  points_count: number;
}

interface OptimizationNodeViewProps {
  node: Record<string, any>;
  depth: number;
}

const STATUS_COLORS: Record<SegmentStatus, string> = {
  idle: 'bg-green-500',
  queued: 'bg-gray-400',
  running: 'bg-yellow-500',
};

const TOTAL_SQUARES = 180;

function OptimizationNodeView({ node, depth }: OptimizationNodeViewProps) {
  const children = Array.isArray(node.children) ? node.children : [];

  return (
    <div className="space-y-1">
      <div className="flex items-start gap-2">
        <div className="mt-[7px] h-[1px] w-3 shrink-0 bg-border-light" style={{ marginLeft: `${depth * 10}px` }} />
        <div className="min-w-0 flex-1 rounded border border-border-light bg-white px-2 py-1">
          <div className="text-xs font-medium text-text-main">{String(node.name || node.optimizer || 'step')}</div>
          <div className="text-[10px] text-text-sub">
            started {node.started_at || '-'} | finished {node.finished_at || '-'} | done {node.done ?? '-'} /{' '}
            {node.total ?? '-'}
          </div>
        </div>
      </div>
      {children.map((child, index) => (
        <OptimizationNodeView key={`${child.name || 'child'}-${index}`} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

interface OptimizationsTabProps {
  collectionName: string;
}

const OptimizationsTab: React.FC<OptimizationsTabProps> = ({ collectionName }) => {
  const { getApiAccessToken } = useAuth();
  const [data, setData] = useState<OptimizationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedUuid, setSelectedUuid] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }
      const result = await qdrantBrowserApi.getOptimizations(token, collectionName);
      setData(result);
    } catch (err: any) {
      setError(err?.message || 'Failed to load optimization data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionName]);

  const segmentSquares = useMemo(() => {
    const result = data?.result || {};
    const segments: Array<{ status: SegmentStatus; points_count: number }> = [];

    (result.idle_segments || []).forEach((segment: any) => {
      segments.push({ status: 'idle', points_count: Number(segment.points_count || 0) });
    });
    (result.queued || []).forEach((optimization: any) => {
      (optimization.segments || []).forEach((segment: any) => {
        segments.push({ status: 'queued', points_count: Number(segment.points_count || 0) });
      });
    });
    (result.running || []).forEach((optimization: any) => {
      (optimization.segments || []).forEach((segment: any) => {
        segments.push({ status: 'running', points_count: Number(segment.points_count || 0) });
      });
    });

    if (segments.length === 0) {
      return [] as SegmentSquare[];
    }

    const totalPoints = segments.reduce((sum, segment) => sum + segment.points_count, 0) || 1;
    const allocated: SegmentSquare[] = [];
    segments.forEach((segment) => {
      const count = Math.max(1, Math.round((segment.points_count / totalPoints) * TOTAL_SQUARES));
      for (let index = 0; index < count; index += 1) {
        allocated.push({ status: segment.status, points_count: segment.points_count });
      }
    });
    return allocated.slice(0, TOTAL_SQUARES);
  }, [data?.result]);

  const timelineItems = useMemo(() => {
    const running = (data?.result?.running || []).map((item: any) => ({ ...item, isRunning: true }));
    const completed = (data?.result?.completed || []).map((item: any) => ({ ...item, isRunning: false }));
    const merged = [...running, ...completed];

    return merged
      .filter((item) => item.progress?.started_at)
      .map((item) => {
        const started = new Date(item.progress.started_at).getTime();
        const finished = item.progress.finished_at ? new Date(item.progress.finished_at).getTime() : Date.now();
        return {
          ...item,
          started,
          finished,
          duration: Math.max(1000, finished - started),
        };
      })
      .sort((a, b) => a.started - b.started);
  }, [data?.result?.completed, data?.result?.running]);

  const selectedOptimization = useMemo(() => {
    if (!selectedUuid && timelineItems.length > 0) {
      return timelineItems[0];
    }
    return timelineItems.find((item) => item.uuid === selectedUuid) || null;
  }, [selectedUuid, timelineItems]);

  const timelineRange = useMemo(() => {
    if (timelineItems.length === 0) {
      return { min: 0, max: 1 };
    }
    const min = Math.min(...timelineItems.map((item) => item.started));
    const max = Math.max(...timelineItems.map((item) => item.finished));
    return { min, max: Math.max(min + 1, max) };
  }, [timelineItems]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-3">
      <div className="rounded border border-border-light bg-white">
        <div className="flex items-center justify-between border-b border-border-light px-3 py-2">
          <div className="text-xs font-semibold text-text-main">Optimization Progress</div>
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs text-text-main hover:bg-surface-light disabled:opacity-40"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
        <div className="p-2">
          {segmentSquares.length === 0 ? (
            <EmptyState title="No optimization segments available" />
          ) : (
            <div className="flex flex-wrap gap-1">
              {segmentSquares.map((square, index) => (
                <div
                  key={`${square.status}-${index}`}
                  title={`${square.status} (${square.points_count} points)`}
                  className={`h-[9px] w-[9px] rounded-[1px] ${STATUS_COLORS[square.status]}`}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="rounded border border-border-light bg-white">
        <div className="border-b border-border-light px-3 py-2 text-xs font-semibold text-text-main">Timeline</div>
        <div className="max-h-[220px] overflow-y-auto p-2">
          {timelineItems.length === 0 ? (
            <EmptyState title="No timeline data" />
          ) : (
            <div className="space-y-1">
              {timelineItems.map((item) => {
                const startRatio = ((item.started - timelineRange.min) / (timelineRange.max - timelineRange.min)) * 100;
                const widthRatio = (item.duration / (timelineRange.max - timelineRange.min)) * 100;
                return (
                  <button
                    type="button"
                    key={String(item.uuid)}
                    onClick={() => setSelectedUuid(item.uuid)}
                    className={`w-full rounded border px-2 py-1 text-left ${
                      selectedOptimization?.uuid === item.uuid
                        ? 'border-primary bg-primary/5'
                        : 'border-border-light bg-white hover:bg-surface-light'
                    }`}
                  >
                    <div className="mb-1 text-xs font-medium text-text-main">
                      {String(item.optimizer || item.progress?.name || 'optimization')}
                      {item.isRunning ? ' (running)' : ''}
                    </div>
                    <div className="relative h-2 rounded bg-border-light">
                      <div
                        className={`absolute h-2 rounded ${item.isRunning ? 'bg-yellow-500' : 'bg-green-600'}`}
                        style={{
                          left: `${Math.min(100, Math.max(0, startRatio))}%`,
                          width: `${Math.min(100, Math.max(1, widthRatio))}%`,
                        }}
                      />
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 rounded border border-border-light bg-white">
        <div className="border-b border-border-light px-3 py-2 text-xs font-semibold text-text-main">Optimization Tree</div>
        <div className="h-full max-h-[calc(100%-33px)] overflow-auto p-2">
          {selectedOptimization?.progress ? (
            <OptimizationNodeView node={selectedOptimization.progress} depth={0} />
          ) : (
            <EmptyState title="No selected optimization" />
          )}
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={refresh} />}
    </div>
  );
};

export default OptimizationsTab;

