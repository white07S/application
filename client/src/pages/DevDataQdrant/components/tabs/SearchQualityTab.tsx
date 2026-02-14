import React, { useMemo, useRef, useState } from 'react';
import { Copy, Play, Square } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { qdrantBrowserApi } from '../../api/qdrantBrowserApi';
import { CollectionInfoResponse, SearchQualityRequest } from '../../types';
import { checkIndexPrecision, normalizeVectorConfig, summarizePrecisions } from '../../utils/searchQuality';
import ErrorState from '../ErrorState';
import EmptyState from '../EmptyState';
import { safeJson } from '../../utils/formatters';

interface SearchQualityTabProps {
  collectionName: string;
  collectionInfo: CollectionInfoResponse | null;
}

const DEFAULT_ADVANCED = {
  limit: 10,
  params: {
    hnsw_ef: 128,
  },
};

const SearchQualityTab: React.FC<SearchQualityTabProps> = ({ collectionName, collectionInfo }) => {
  const { getApiAccessToken } = useAuth();
  const [advancedMode, setAdvancedMode] = useState(false);
  const [advancedInput, setAdvancedInput] = useState(safeJson(DEFAULT_ADVANCED));
  const [precisionByVector, setPrecisionByVector] = useState<Record<string, number | null>>({});
  const [logLines, setLogLines] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const runIdRef = useRef(0);

  const vectorConfig = useMemo(() => normalizeVectorConfig(collectionInfo?.info || {}), [collectionInfo?.info]);
  const vectorNames = useMemo(() => {
    const names = Object.keys(vectorConfig);
    return names.length > 0 ? names : ['default'];
  }, [vectorConfig]);

  const appendLog = (line: string) => {
    const ts = new Date().toLocaleTimeString();
    setLogLines((current) => [`[${ts}] ${line}`, ...current]);
  };

  const stopRun = () => {
    runIdRef.current += 1;
    setRunning(false);
    appendLog('Quality run canceled');
  };

  const runQuality = async (request: SearchQualityRequest, vectorLabel: string) => {
    const runId = runIdRef.current + 1;
    runIdRef.current = runId;
    setRunning(true);
    setError(null);
    setLogLines([]);

    try {
      const token = await getApiAccessToken();
      if (!token) {
        setRunning(false);
        return;
      }

      const scroll = await qdrantBrowserApi.scrollPoints(token, collectionName, {
        limit: request.limit,
        with_payload: false,
        with_vector: false,
        filter: request.filter || undefined,
      });

      const pointIds = scroll.points.map((point) => point.id);
      appendLog(`Running ${pointIds.length} precision checks for vector "${vectorLabel}"`);

      const precisions: number[] = [];
      for (let index = 0; index < pointIds.length; index += 1) {
        if (runIdRef.current !== runId) {
          return;
        }

        const pointId = pointIds[index];
        const result = await checkIndexPrecision(token, collectionName, pointId, request);
        precisions.push(result.precision);
        appendLog(
          `#${index + 1}/${pointIds.length} id=${String(pointId)} precision@${request.limit}=${result.precision.toFixed(
            4
          )} (exact ${result.exactElapsedMs}ms / approx ${result.approxElapsedMs}ms)`
        );
      }

      const summary = summarizePrecisions(precisions);
      appendLog(`Mean precision@${request.limit}: ${summary.mean} +/- ${summary.stdDev}`);
      setPrecisionByVector((current) => ({
        ...current,
        [vectorLabel]: summary.mean,
      }));
    } catch (err: any) {
      const message = err?.message || 'Failed to run search quality checks';
      setError(message);
      appendLog(`Error: ${message}`);
    } finally {
      if (runIdRef.current === runId) {
        setRunning(false);
      }
    }
  };

  if (!collectionInfo) {
    return <EmptyState title="Collection info unavailable" />;
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-3">
      <div className="rounded border border-border-light bg-white">
        <div className="flex items-center justify-between border-b border-border-light px-3 py-2">
          <div className="text-xs font-semibold text-text-main">Search Quality</div>
          <div className="flex items-center gap-2">
            <label className="inline-flex items-center gap-1 text-xs text-text-sub">
              <input
                type="checkbox"
                checked={advancedMode}
                onChange={(event) => setAdvancedMode(event.target.checked)}
                className="h-3.5 w-3.5"
              />
              Advanced mode
            </label>
            <button
              type="button"
              onClick={() => navigator.clipboard.writeText(logLines.join('\n'))}
              className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
            >
              <Copy size={12} />
              Copy Log
            </button>
          </div>
        </div>

        {!advancedMode ? (
          <div className="overflow-x-auto p-2">
            <table className="w-full min-w-[620px] text-xs">
              <thead>
                <tr className="text-left text-text-sub">
                  <th className="px-2 py-1 font-medium">Vector</th>
                  <th className="px-2 py-1 font-medium">Size</th>
                  <th className="px-2 py-1 font-medium">Distance</th>
                  <th className="px-2 py-1 font-medium">Precision</th>
                  <th className="px-2 py-1 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {vectorNames.map((vectorName) => {
                  const config = vectorConfig[vectorName] || {};
                  const normalizedVector = vectorName === 'default' ? null : vectorName;
                  return (
                    <tr key={vectorName} className="border-t border-border-light">
                      <td className="px-2 py-1 font-mono text-text-main">{vectorName}</td>
                      <td className="px-2 py-1 text-text-sub">{config.size ?? '-'}</td>
                      <td className="px-2 py-1 text-text-sub">{config.distance ?? '-'}</td>
                      <td className="px-2 py-1 text-text-main">
                        {precisionByVector[vectorName] == null ? '-' : `${(precisionByVector[vectorName] || 0) * 100}%`}
                      </td>
                      <td className="px-2 py-1">
                        <button
                          type="button"
                          disabled={running}
                          onClick={() =>
                            runQuality(
                              {
                                limit: 10,
                                using: normalizedVector,
                                params: { hnsw_ef: 128 },
                              },
                              vectorName
                            )
                          }
                          className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light disabled:opacity-40"
                        >
                          <Play size={12} />
                          Check
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="space-y-2 p-2">
            <div className="text-[10px] uppercase text-text-sub">
              Request JSON ({`{ limit, using, filter, params, timeout }`})
            </div>
            <textarea
              value={advancedInput}
              onChange={(event) => setAdvancedInput(event.target.value)}
              className="h-44 w-full resize-none rounded border border-border-light bg-white p-2 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-primary/35"
            />
            <button
              type="button"
              disabled={running}
              onClick={() => {
                try {
                  const parsed = JSON.parse(advancedInput) as SearchQualityRequest;
                  const normalized = {
                    limit: parsed.limit || 10,
                    using: parsed.using || null,
                    filter: parsed.filter || null,
                    params: parsed.params || null,
                    timeout: parsed.timeout || 20,
                  };
                  const vectorLabel = normalized.using || 'default';
                  runQuality(normalized, vectorLabel);
                } catch {
                  setError('Invalid JSON payload for advanced mode');
                }
              }}
              className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light disabled:opacity-40"
            >
              <Play size={12} />
              Run Advanced
            </button>
          </div>
        )}
      </div>

      {error && <ErrorState message={error} />}

      <div className="min-h-0 flex-1 rounded border border-border-light bg-white">
        <div className="flex items-center justify-between border-b border-border-light px-3 py-2">
          <div className="text-xs font-semibold text-text-main">Report</div>
          <button
            type="button"
            onClick={running ? stopRun : undefined}
            disabled={!running}
            className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light disabled:opacity-40"
          >
            <Square size={12} />
            Stop
          </button>
        </div>
        <pre className="h-full max-h-[calc(100%-33px)] overflow-auto p-3 text-[11px] leading-[1.4] text-text-main">
          {logLines.length > 0 ? logLines.join('\n') : 'No runs yet'}
        </pre>
      </div>
    </div>
  );
};

export default SearchQualityTab;

