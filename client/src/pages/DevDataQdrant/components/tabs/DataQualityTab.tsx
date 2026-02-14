import React, { useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { qdrantBrowserApi } from '../../api/qdrantBrowserApi';
import { CollectionInfoResponse, PayloadFieldQuality, PayloadQualityResponse } from '../../types';
import ErrorState from '../ErrorState';
import EmptyState from '../EmptyState';
import { formatNumber, safeJson } from '../../utils/formatters';
import { useQdrantBrowserStore } from '../../store/useQdrantBrowserStore';
import { buildQdrantFilter } from '../../utils/filterParser';

interface DataQualityTabProps {
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

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return 'null';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function topValuesSummary(field: PayloadFieldQuality): string {
  if (!field.top_values || field.top_values.length === 0) {
    return '-';
  }

  return field.top_values
    .slice(0, 5)
    .map((entry) => `${formatValue(entry.value)} (${formatPct(entry.pct)})`)
    .join(' | ');
}

const DataQualityTab: React.FC<DataQualityTabProps> = ({ collectionName, collectionInfo }) => {
  const { getApiAccessToken } = useAuth();
  const { payloadFilters } = useQdrantBrowserStore();
  const [sampleLimit, setSampleLimit] = useState(500);
  const [result, setResult] = useState<PayloadQualityResponse | null>(null);
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

      const response = await qdrantBrowserApi.getPayloadQuality(token, collectionName, {
        sample_limit: sampleLimit,
        filter: activeFilter,
      });
      setResult(response);
    } catch (err: any) {
      setError(err?.message || 'Failed to load payload quality insights');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionName, sampleLimit, payloadFilters, payloadSchemaJson]);

  const summary = useMemo(() => {
    const fields = result?.fields || [];
    const conflictCount = fields.filter((field) => field.type_conflicts.length > 0).length;
    const lowCoverageCount = fields.filter((field) => field.coverage_pct < 90).length;
    const highNullCount = fields.filter((field) => field.null_pct >= 25).length;

    return {
      totalFields: fields.length,
      conflictCount,
      lowCoverageCount,
      highNullCount,
      samplePoints: result?.sample_points || 0,
    };
  }, [result]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-3">
      <div className="rounded border border-border-light bg-white">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-light px-3 py-2">
          <div>
            <div className="text-xs font-semibold text-text-main">Data Quality by Payload Field</div>
            <div className="text-[11px] text-text-sub">Coverage, null/empty rates, top values, and type conflicts.</div>
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

        <div className="grid grid-cols-2 gap-2 p-2 text-[11px] lg:grid-cols-5">
          <div className="rounded border border-border-light bg-surface-light px-2 py-1">
            <div className="text-text-sub">Sampled Points</div>
            <div className="font-semibold text-text-main">{formatNumber(summary.samplePoints)}</div>
          </div>
          <div className="rounded border border-border-light bg-surface-light px-2 py-1">
            <div className="text-text-sub">Fields</div>
            <div className="font-semibold text-text-main">{formatNumber(summary.totalFields)}</div>
          </div>
          <div className="rounded border border-border-light bg-surface-light px-2 py-1">
            <div className="text-text-sub">Type Conflicts</div>
            <div className="font-semibold text-text-main">{formatNumber(summary.conflictCount)}</div>
          </div>
          <div className="rounded border border-border-light bg-surface-light px-2 py-1">
            <div className="text-text-sub">Coverage &lt; 90%</div>
            <div className="font-semibold text-text-main">{formatNumber(summary.lowCoverageCount)}</div>
          </div>
          <div className="rounded border border-border-light bg-surface-light px-2 py-1">
            <div className="text-text-sub">Null &gt;= 25%</div>
            <div className="font-semibold text-text-main">{formatNumber(summary.highNullCount)}</div>
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
          <div className="flex h-full items-center justify-center text-xs text-text-sub">Loading payload quality...</div>
        ) : !result || result.fields.length === 0 ? (
          <EmptyState title="No payload fields sampled" description="Try a larger sample size or another collection." />
        ) : (
          <div className="h-full overflow-auto">
            <table className="w-full min-w-[980px] text-xs">
              <thead className="sticky top-0 bg-white text-left text-text-sub">
                <tr>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Field</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Coverage</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Null</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Empty</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Distinct</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Type Conflicts</th>
                  <th className="border-b border-border-light px-2 py-1 font-medium">Top Values</th>
                </tr>
              </thead>
              <tbody>
                {result.fields.map((field) => (
                  <tr key={field.field} className="border-b border-border-light/70 align-top">
                    <td className="px-2 py-1 font-mono text-text-main">{field.field}</td>
                    <td className="px-2 py-1 text-text-main">{formatPct(field.coverage_pct)}</td>
                    <td className="px-2 py-1 text-text-main">{formatPct(field.null_pct)}</td>
                    <td className="px-2 py-1 text-text-main">{formatPct(field.empty_pct)}</td>
                    <td className="px-2 py-1 text-text-main">{formatNumber(field.distinct_count)}</td>
                    <td className="px-2 py-1 text-text-main">
                      {field.type_conflicts.length > 0 ? field.type_conflicts.join(', ') : '-'}
                    </td>
                    <td className="max-w-[520px] px-2 py-1 text-text-sub" title={topValuesSummary(field)}>
                      <span className="line-clamp-2">{topValuesSummary(field)}</span>
                    </td>
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

export default DataQualityTab;
