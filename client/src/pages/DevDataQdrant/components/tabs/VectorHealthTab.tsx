import React, { useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { qdrantBrowserApi } from '../../api/qdrantBrowserApi';
import { CollectionInfoResponse, VectorHealthEntry, VectorHealthResponse } from '../../types';
import ErrorState from '../ErrorState';
import EmptyState from '../EmptyState';
import { formatNumber, safeJson } from '../../utils/formatters';
import { useQdrantBrowserStore } from '../../store/useQdrantBrowserStore';
import { buildQdrantFilter } from '../../utils/filterParser';

interface VectorHealthTabProps {
  collectionName: string;
  collectionInfo: CollectionInfoResponse | null;
}

const SAMPLE_OPTIONS = [500, 1000, 2000, 5000];

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-';
  }
  return `${value.toFixed(2)}%`;
}

function formatNorm(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-';
  }
  return value.toFixed(4);
}

const VectorHealthTab: React.FC<VectorHealthTabProps> = ({ collectionName, collectionInfo }) => {
  const { getApiAccessToken } = useAuth();
  const { payloadFilters } = useQdrantBrowserStore();
  const [sampleLimit, setSampleLimit] = useState(500);
  const [result, setResult] = useState<VectorHealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const payloadSchema = useMemo(() => collectionInfo?.payload_schema || {}, [collectionInfo?.payload_schema]);
  const payloadSchemaJson = useMemo(() => safeJson(payloadSchema), [payloadSchema]);
  const activeFilter = useMemo(() => buildQdrantFilter(payloadFilters, payloadSchema), [payloadFilters, payloadSchema]);

  const refresh = async () => {
    setLoading(true);
    setError(null);

    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }

      const response = await qdrantBrowserApi.getVectorHealth(token, collectionName, {
        sample_limit: sampleLimit,
        filter: activeFilter,
      });
      setResult(response);
    } catch (err: any) {
      setError(err?.message || 'Failed to load vector health insights');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionName, sampleLimit, payloadFilters, payloadSchemaJson]);

  const summary = useMemo(() => {
    const vectors = result?.vectors || [];
    const mismatchCount = vectors.reduce((sum, entry) => sum + entry.dimension_mismatch_count, 0);
    const unsupportedCount = vectors.reduce((sum, entry) => sum + entry.unsupported_format_count, 0);

    return {
      sampledPoints: result?.sample_points || 0,
      vectors: vectors.length,
      mismatchCount,
      unsupportedCount,
    };
  }, [result]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-3">
      <div className="rounded border border-border-light bg-white">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-light px-3 py-2">
          <div>
            <div className="text-xs font-semibold text-text-main">Vector Health</div>
            <div className="text-[11px] text-text-sub">Missing rate, dimension mismatches, zero vectors, and norm percentiles.</div>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-[11px] text-text-sub">
              Sample
              <select
                value={sampleLimit}
                onChange={(event) => setSampleLimit(Number(event.target.value) || 500)}
                className="ml-1 rounded border border-border-light bg-white px-2 py-1 text-xs text-text-main"
              >
                {SAMPLE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {formatNumber(option)}
                  </option>
                ))}
              </select>
            </label>
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
        </div>

        <div className="grid grid-cols-2 gap-2 p-2 text-[11px] lg:grid-cols-4">
          <div className="rounded border border-border-light bg-surface-light px-2 py-1">
            <div className="text-text-sub">Sampled Points</div>
            <div className="font-semibold text-text-main">{formatNumber(summary.sampledPoints)}</div>
          </div>
          <div className="rounded border border-border-light bg-surface-light px-2 py-1">
            <div className="text-text-sub">Vectors</div>
            <div className="font-semibold text-text-main">{formatNumber(summary.vectors)}</div>
          </div>
          <div className="rounded border border-border-light bg-surface-light px-2 py-1">
            <div className="text-text-sub">Dimension Mismatches</div>
            <div className="font-semibold text-text-main">{formatNumber(summary.mismatchCount)}</div>
          </div>
          <div className="rounded border border-border-light bg-surface-light px-2 py-1">
            <div className="text-text-sub">Unsupported Formats</div>
            <div className="font-semibold text-text-main">{formatNumber(summary.unsupportedCount)}</div>
          </div>
        </div>

        {payloadFilters.length > 0 && (
          <div className="border-t border-border-light px-2 py-1 text-[11px] text-text-sub">
            Scoped by {payloadFilters.length} active filter{payloadFilters.length === 1 ? '' : 's'} from Points tab.
          </div>
        )}
      </div>

      {error && <ErrorState message={error} onRetry={refresh} />}

      <div className="min-h-0 flex-1 rounded border border-border-light bg-white">
        {loading ? (
          <div className="flex h-full items-center justify-center text-xs text-text-sub">Loading vector health...</div>
        ) : !result || result.vectors.length === 0 ? (
          <EmptyState title="No vectors sampled" description="Try a larger sample size or another collection." />
        ) : (
          <div className="h-full overflow-auto">
            <table className="w-full min-w-[1180px] text-xs">
              <thead className="sticky top-0 bg-white text-left text-text-sub">
                <tr>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Vector</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Expected Dim</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Present</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Missing</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Dim Mismatch</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Unsupported</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Zero Vectors</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Norm P05</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Norm P25</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Norm P50</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Norm P75</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Norm P95</th>
                </tr>
              </thead>
              <tbody>
                {result.vectors.map((entry: VectorHealthEntry) => (
                  <tr key={entry.vector_name} className="border-b border-border-light/70">
                    <td className="px-2 py-1 font-mono text-text-main">{entry.vector_name}</td>
                    <td className="px-2 py-1 text-text-main">{entry.expected_dim ?? '-'}</td>
                    <td className="px-2 py-1 text-text-main">
                      {formatNumber(entry.present_count)} / {formatNumber(entry.points_seen)}
                    </td>
                    <td className="px-2 py-1 text-text-main">{formatPct(entry.missing_rate_pct)}</td>
                    <td className="px-2 py-1 text-text-main">{formatNumber(entry.dimension_mismatch_count)}</td>
                    <td className="px-2 py-1 text-text-main">{formatNumber(entry.unsupported_format_count)}</td>
                    <td className="px-2 py-1 text-text-main">{formatPct(entry.zero_vector_rate_pct)}</td>
                    <td className="px-2 py-1 text-text-main">{formatNorm(entry.norm_percentiles.p05)}</td>
                    <td className="px-2 py-1 text-text-main">{formatNorm(entry.norm_percentiles.p25)}</td>
                    <td className="px-2 py-1 text-text-main">{formatNorm(entry.norm_percentiles.p50)}</td>
                    <td className="px-2 py-1 text-text-main">{formatNorm(entry.norm_percentiles.p75)}</td>
                    <td className="px-2 py-1 text-text-main">{formatNorm(entry.norm_percentiles.p95)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default VectorHealthTab;
