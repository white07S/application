import React, { useEffect, useMemo, useState } from 'react';
import { Copy, Search, SlidersHorizontal } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { qdrantBrowserApi } from '../../api/qdrantBrowserApi';
import {
  CollectionInfoResponse,
  PayloadSchemaEntry,
  PointId,
  PointRecord,
} from '../../types';
import {
  buildFilterInputFromFilters,
  buildQdrantFilter,
  parseFilterString,
  parseSimilarInput,
} from '../../utils/filterParser';
import { useQdrantBrowserStore } from '../../store/useQdrantBrowserStore';
import EmptyState from '../EmptyState';
import ErrorState from '../ErrorState';
import { safeJson } from '../../utils/formatters';

const PAGE_SIZE = 20;

interface PointsTabProps {
  collectionName: string;
  collectionInfo: CollectionInfoResponse | null;
  onOpenGraph: (point: PointRecord, vectorName: string | null) => void;
}

function vectorEntries(point: PointRecord): Array<{ name: string | null; value: any }> {
  const vector = point.vector;
  if (!vector) {
    return [];
  }
  if (Array.isArray(vector)) {
    return [{ name: null, value: vector }];
  }
  if (typeof vector === 'object') {
    return Object.entries(vector).map(([name, value]) => ({ name, value }));
  }
  return [];
}

function vectorLength(value: any): string {
  if (Array.isArray(value) && Array.isArray(value[0])) {
    return `${value.length}x${value[0].length}`;
  }
  if (Array.isArray(value)) {
    return String(value.length);
  }
  if (value && Array.isArray(value.indices)) {
    return String(value.indices.length);
  }
  return '-';
}

function normalizeSimilarInput(raw: string): PointId[] {
  const values = raw
    .split(/[,\s]+/)
    .map((token) => token.trim())
    .filter(Boolean)
    .map((token) => parseSimilarInput(token))
    .filter((value): value is PointId => value !== null);

  return Array.from(new Set(values));
}

const PointsTab: React.FC<PointsTabProps> = ({ collectionName, collectionInfo, onOpenGraph }) => {
  const { getApiAccessToken } = useAuth();
  const {
    similarIds,
    payloadFilters,
    usingVector,
    similarityLimit,
    setSimilarIds,
    setPayloadFilters,
    setUsingVector,
    increaseSimilarityLimit,
    setSelectedPoint,
  } = useQdrantBrowserStore();

  const [points, setPoints] = useState<PointRecord[]>([]);
  const [nextOffset, setNextOffset] = useState<PointId | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterInput, setFilterInput] = useState(buildFilterInputFromFilters(payloadFilters));
  const [similarInput, setSimilarInput] = useState(similarIds.join(' '));
  const [facetValues, setFacetValues] = useState<Record<string, Array<string | number | boolean | null>>>({});

  const payloadSchema = collectionInfo?.payload_schema || {};

  const hasNamedVectors = (collectionInfo?.named_vectors?.length || 0) > 0;
  const vectorNames = useMemo(() => {
    const configured = collectionInfo?.named_vectors || [];
    return configured.length > 0 ? configured : ['default'];
  }, [collectionInfo?.named_vectors]);
  const effectiveUsingVector = useMemo(() => {
    if (!hasNamedVectors) {
      return usingVector || 'default';
    }
    if (usingVector && vectorNames.includes(usingVector)) {
      return usingVector;
    }
    return vectorNames[0];
  }, [hasNamedVectors, usingVector, vectorNames]);

  useEffect(() => {
    setFilterInput(buildFilterInputFromFilters(payloadFilters));
  }, [payloadFilters]);

  useEffect(() => {
    setSimilarInput(similarIds.join(' '));
  }, [similarIds]);

  useEffect(() => {
    if (!hasNamedVectors) {
      return;
    }
    if (!usingVector || !vectorNames.includes(usingVector)) {
      setUsingVector(vectorNames[0]);
    }
  }, [hasNamedVectors, setUsingVector, usingVector, vectorNames]);

  const loadFacetValues = async () => {
    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }

      const keywordFields = Object.entries(payloadSchema)
        .filter(([, schema]) => (schema as PayloadSchemaEntry)?.data_type === 'keyword')
        .map(([key]) => key);

      if (keywordFields.length === 0) {
        setFacetValues({});
        return;
      }

      const responses = await Promise.all(
        keywordFields.map(async (key) => {
          try {
            const result = await qdrantBrowserApi.facet(token, collectionName, { key, limit: 50 });
            const values = (result.hits || []).map((item) => item.value);
            return [key, values] as const;
          } catch {
            return [key, []] as const;
          }
        })
      );

      setFacetValues(Object.fromEntries(responses));
    } catch {
      setFacetValues({});
    }
  };

  const loadPoints = async (append = false) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setError(null);
    }

    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }

      const filter = buildQdrantFilter(payloadFilters, payloadSchema);

      if (similarIds.length > 0) {
        const queryResult = await qdrantBrowserApi.queryPoints(token, collectionName, {
          query: {
            recommend: {
              positive: similarIds,
            },
          },
          limit: similarityLimit,
          with_payload: true,
          with_vector: true,
          using: effectiveUsingVector && effectiveUsingVector !== 'default' ? effectiveUsingVector : undefined,
          filter,
        });
        setPoints(queryResult.points || []);
        setNextOffset(queryResult.points.length >= similarityLimit ? queryResult.points.length : null);
      } else {
        const scrollResult = await qdrantBrowserApi.scrollPoints(token, collectionName, {
          offset: append ? nextOffset : undefined,
          filter,
          limit: PAGE_SIZE,
          with_payload: true,
          with_vector: true,
        });
        const incoming = scrollResult.points || [];
        setPoints((current) => (append ? [...current, ...incoming] : incoming));
        setNextOffset(scrollResult.next_page_offset ?? null);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load points');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    loadPoints(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionName, similarIds, payloadFilters, effectiveUsingVector, similarityLimit]);

  useEffect(() => {
    loadFacetValues();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionName, safeJson(payloadSchema)]);

  const applyFilters = () => {
    const parsed = parseFilterString(filterInput, payloadSchema);
    setPayloadFilters(parsed);
  };

  const clearFilters = () => {
    setFilterInput('');
    setPayloadFilters([]);
  };

  const applySimilarIds = () => {
    setSimilarIds(normalizeSimilarInput(similarInput));
  };

  const clearSimilarIds = () => {
    setSimilarInput('');
    setSimilarIds([]);
  };

  const findSimilarFromPoint = (pointId: PointId, vectorName: string | null) => {
    setSimilarIds([pointId]);
    setSimilarInput(String(pointId));
    if (hasNamedVectors) {
      setUsingVector(vectorName || vectorNames[0]);
      return;
    }
    setUsingVector(vectorName || null);
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 overflow-hidden p-3">
      <div className="rounded border border-border-light bg-white p-2">
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-12">
          <div className="lg:col-span-3">
            <div className="mb-1 text-[10px] uppercase text-text-sub">Similar IDs</div>
            <div className="flex items-center gap-1">
              <input
                value={similarInput}
                onChange={(event) => setSimilarInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    applySimilarIds();
                  }
                }}
                placeholder="id:123 or 123 456"
                className="w-full rounded border border-border-light px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary/35"
              />
              <button
                type="button"
                onClick={applySimilarIds}
                className="rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
              >
                Apply
              </button>
              <button
                type="button"
                onClick={clearSimilarIds}
                className="rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="mb-1 text-[10px] uppercase text-text-sub">Payload filter (key:value, id:123)</div>
            <div className="flex items-center gap-1">
              <input
                value={filterInput}
                onChange={(event) => setFilterInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    applyFilters();
                  }
                }}
                placeholder="status:active id:123 owner:ops"
                className="w-full rounded border border-border-light px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary/35"
              />
              <button
                type="button"
                onClick={applyFilters}
                className="rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
              >
                Apply
              </button>
              <button
                type="button"
                onClick={clearFilters}
                className="rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="lg:col-span-3">
            <div className="mb-1 text-[10px] uppercase text-text-sub">Vector</div>
            <select
              value={effectiveUsingVector}
              onChange={(event) => {
                const value = event.target.value;
                if (!hasNamedVectors) {
                  setUsingVector(value === 'default' ? null : value);
                  return;
                }
                setUsingVector(value);
              }}
              className="w-full rounded border border-border-light bg-white px-2 py-1 text-xs"
            >
              {vectorNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {Object.keys(facetValues).length > 0 && (
          <div className="mt-2 border-t border-border-light pt-2">
            <div className="mb-1 text-[10px] uppercase text-text-sub">Facet values (keyword fields)</div>
            <div className="flex flex-wrap gap-2 text-[11px] text-text-sub">
              {Object.entries(facetValues).map(([key, values]) => (
                <div key={key} className="rounded border border-border-light bg-surface-light px-2 py-1">
                  <span className="font-mono text-text-main">{key}</span>: {values.slice(0, 5).map(String).join(', ')}
                  {values.length > 5 ? ' ...' : ''}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {error && <ErrorState message={error} onRetry={() => loadPoints(false)} />}

      {loading ? (
        <div className="flex min-h-0 flex-1 items-center justify-center rounded border border-border-light bg-white text-xs text-text-sub">
          Loading points...
        </div>
      ) : points.length === 0 ? (
        <EmptyState title="No points found" description="Adjust filters or select another collection." />
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto rounded border border-border-light bg-white">
          <div className="space-y-2 p-2">
            {points.map((point) => {
              const vectors = vectorEntries(point);
              return (
                <div
                  key={String(point.id)}
                  className="rounded border border-border-light bg-surface-light/50"
                >
                  <div className="flex items-center justify-between border-b border-border-light px-2 py-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-text-main">Point</span>
                      <span className="text-xs font-mono text-text-main">{String(point.id)}</span>
                      {typeof point.score === 'number' && (
                        <span className="rounded bg-white px-1.5 py-0.5 text-[10px] text-text-sub">
                          score {point.score.toFixed(4)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => navigator.clipboard.writeText(safeJson(point))}
                        className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-[11px] hover:bg-surface-light"
                      >
                        <Copy size={12} />
                        JSON
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedPoint(point)}
                        className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-[11px] hover:bg-surface-light"
                      >
                        <SlidersHorizontal size={12} />
                        Preview
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-2 p-2 xl:grid-cols-2">
                    <div className="rounded border border-border-light bg-white p-2">
                      <div className="mb-1 text-[10px] uppercase text-text-sub">Payload</div>
                      <pre className="max-h-[180px] overflow-auto text-[11px] text-text-main">
                        {safeJson(point.payload || {})}
                      </pre>
                    </div>
                    <div className="rounded border border-border-light bg-white p-2">
                      <div className="mb-1 text-[10px] uppercase text-text-sub">Vectors</div>
                      <div className="space-y-1">
                        {vectors.length === 0 && <div className="text-xs text-text-sub">No vector data</div>}
                        {vectors.map((entry) => (
                          <div
                            key={`${String(point.id)}-${entry.name || 'default'}`}
                            className="flex items-center justify-between gap-2 rounded border border-border-light px-2 py-1"
                          >
                            <div className="min-w-0 text-xs text-text-main">
                              <div className="font-mono">{entry.name || 'default'}</div>
                              <div className="text-[10px] text-text-sub">len {vectorLength(entry.value)}</div>
                            </div>
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => findSimilarFromPoint(point.id, entry.name)}
                                className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-[11px] hover:bg-surface-light"
                              >
                                <Search size={11} />
                                Similar
                              </button>
                              <button
                                type="button"
                                onClick={() => onOpenGraph(point, entry.name)}
                                className="rounded border border-border-light bg-white px-2 py-1 text-[11px] hover:bg-surface-light"
                              >
                                Graph
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex items-center justify-center">
        <button
          type="button"
          disabled={loadingMore || !nextOffset}
          onClick={() => {
            if (similarIds.length > 0) {
              increaseSimilarityLimit(PAGE_SIZE);
              return;
            }
            loadPoints(true);
          }}
          className="rounded border border-border-light bg-white px-3 py-1 text-xs text-text-main hover:bg-surface-light disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loadingMore ? 'Loading...' : 'Load More'}
        </button>
      </div>
    </div>
  );
};

export default PointsTab;
