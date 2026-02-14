import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Copy, Play, RefreshCw } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { qdrantBrowserApi } from '../../api/qdrantBrowserApi';
import { CollectionInfoResponse, PointRecord, VisualizeRequest } from '../../types';
import ErrorState from '../ErrorState';
import EmptyState from '../EmptyState';
import { safeJson } from '../../utils/formatters';
import { useQdrantBrowserStore } from '../../store/useQdrantBrowserStore';

interface VisualizeTabProps {
  collectionName: string;
  collectionInfo: CollectionInfoResponse | null;
}

interface ReducedPoint {
  x: number;
  y: number;
}

const DEFAULT_REQUEST: VisualizeRequest = {
  limit: 300,
  algorithm: 'UMAP',
};

const COLOR_SCALE = ['#e60000', '#0097cc', '#498100', '#e5b01c', '#c81219', '#6b7280', '#00a3a3', '#1f78ff'];
const SCORE_GRADIENT = ['#EB5353', '#F9D923', '#36AE7C'];
const DEFAULT_POINT_COLOR = '#2563eb';

function normalizeCoordinates(points: ReducedPoint[]) {
  if (points.length === 0) {
    return [];
  }
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = maxX - minX || 1;
  const height = maxY - minY || 1;

  return points.map((point) => ({
    x: ((point.x - minX) / width) * 960 + 20,
    y: ((point.y - minY) / height) * 560 + 20,
  }));
}

function getNestedValue(obj: Record<string, any> | undefined, path: string): unknown {
  return path.split('.').reduce((acc: any, part) => (acc && typeof acc === 'object' ? acc[part] : undefined), obj);
}

function hasQueryColorBy(colorBy: VisualizeRequest['color_by']): colorBy is { query?: unknown; payload?: string } {
  return Boolean(colorBy && typeof colorBy === 'object' && 'query' in colorBy && (colorBy as any).query);
}

function payloadPath(colorBy: VisualizeRequest['color_by']): string | null {
  if (!colorBy) {
    return null;
  }
  if (typeof colorBy === 'string') {
    return colorBy;
  }
  if (typeof colorBy === 'object' && typeof colorBy.payload === 'string' && colorBy.payload) {
    return colorBy.payload;
  }
  return null;
}

function hexToRgb(hex: string): [number, number, number] {
  const normalized = hex.replace('#', '');
  const r = parseInt(normalized.slice(0, 2), 16);
  const g = parseInt(normalized.slice(2, 4), 16);
  const b = parseInt(normalized.slice(4, 6), 16);
  return [r, g, b];
}

function rgbToHex([r, g, b]: [number, number, number]): string {
  const toHex = (value: number) => value.toString(16).padStart(2, '0');
  return `#${toHex(Math.round(r))}${toHex(Math.round(g))}${toHex(Math.round(b))}`;
}

function lerpColor(start: string, end: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(start);
  const [r2, g2, b2] = hexToRgb(end);
  return rgbToHex([
    r1 + (r2 - r1) * t,
    g1 + (g2 - g1) * t,
    b1 + (b2 - b1) * t,
  ]);
}

function scoreToColor(score: number, minScore: number, maxScore: number): string {
  if (maxScore <= minScore) {
    return SCORE_GRADIENT[1];
  }
  const normalized = (score - minScore) / (maxScore - minScore);
  if (normalized <= 0.5) {
    return lerpColor(SCORE_GRADIENT[0], SCORE_GRADIENT[1], normalized * 2);
  }
  return lerpColor(SCORE_GRADIENT[1], SCORE_GRADIENT[2], (normalized - 0.5) * 2);
}

function colorBy(points: PointRecord[], request: VisualizeRequest): string[] {
  if (hasQueryColorBy(request.color_by)) {
    const scores = points.map((point) => (typeof point.score === 'number' ? point.score : 0));
    const minScore = Math.min(...scores);
    const maxScore = Math.max(...scores);
    return scores.map((score) => scoreToColor(score, minScore, maxScore));
  }

  const path = payloadPath(request.color_by);
  if (!path) {
    return points.map(() => DEFAULT_POINT_COLOR);
  }

  const unique = Array.from(new Set(points.map((point) => String(getNestedValue(point.payload, path) ?? 'unknown'))));
  const map = new Map<string, string>();
  unique.forEach((key, index) => map.set(key, COLOR_SCALE[index % COLOR_SCALE.length]));
  return points.map((point) => map.get(String(getNestedValue(point.payload, path) ?? 'unknown')) || DEFAULT_POINT_COLOR);
}

const VisualizeTab: React.FC<VisualizeTabProps> = ({ collectionName, collectionInfo }) => {
  const { getApiAccessToken } = useAuth();
  const { visualizeRequest, setVisualizeRequest, setSelectedPoint } = useQdrantBrowserStore();
  const [requestInput, setRequestInput] = useState(safeJson(visualizeRequest || DEFAULT_REQUEST));
  const [points, setPoints] = useState<PointRecord[]>([]);
  const [reduced, setReduced] = useState<ReducedPoint[]>([]);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const workerRef = useRef<Worker | null>(null);
  const namedVectors = useMemo(() => collectionInfo?.named_vectors || [], [collectionInfo?.named_vectors]);

  const normalizeRequestUsing = useCallback((request: VisualizeRequest): VisualizeRequest => {
    if (namedVectors.length === 0) {
      return {
        ...request,
        using: request.using || null,
      };
    }
    if (request.using && namedVectors.includes(request.using)) {
      return request;
    }
    return {
      ...request,
      using: namedVectors[0],
    };
  }, [namedVectors]);

  useEffect(() => {
    const next = normalizeRequestUsing(visualizeRequest || DEFAULT_REQUEST);
    setRequestInput(safeJson(next));
  }, [collectionName, normalizeRequestUsing, visualizeRequest]);

  useEffect(() => {
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
      }
    };
  }, []);

  const runRequest = async (request: VisualizeRequest) => {
    setLoading(true);
    setError(null);
    setReduced([]);
    setActiveIndex(null);

    try {
      const token = await getApiAccessToken();
      if (!token) {
        setLoading(false);
        return;
      }

      const effectiveRequest = normalizeRequestUsing(request);
      let resultPoints: PointRecord[] = [];
      if (hasQueryColorBy(effectiveRequest.color_by)) {
        const queryResponse = await qdrantBrowserApi.queryPoints(token, collectionName, {
          query: effectiveRequest.color_by.query,
          limit: effectiveRequest.limit,
          with_payload: true,
          with_vector: effectiveRequest.using ? [effectiveRequest.using] : true,
          using: effectiveRequest.using || undefined,
          filter: effectiveRequest.filter || undefined,
        });
        resultPoints = queryResponse.points || [];
      } else {
        const scrollResponse = await qdrantBrowserApi.scrollPoints(token, collectionName, {
          limit: effectiveRequest.limit,
          filter: effectiveRequest.filter || undefined,
          with_payload: true,
          with_vector: effectiveRequest.using ? [effectiveRequest.using] : true,
        });
        resultPoints = scrollResponse.points || [];
      }

      if (resultPoints.length < 2) {
        setPoints(resultPoints);
        setReduced([]);
        setLoading(false);
        setError('Need at least 2 points to visualize');
        return;
      }

      setPoints(resultPoints);

      if (workerRef.current) {
        workerRef.current.terminate();
      }

      const worker = new Worker(new URL('../visualize/visualize.worker.js', import.meta.url));
      workerRef.current = worker;
      worker.onmessage = (event: MessageEvent) => {
        const { result, error: workerError } = event.data || {};
        if (workerError) {
          setError(workerError);
          setLoading(false);
          return;
        }
        if (Array.isArray(result)) {
          setReduced(result);
          setLoading(false);
        }
      };
      worker.onerror = () => {
        setError('Visualization worker failed');
        setLoading(false);
      };
      worker.postMessage({
        points: resultPoints,
        params: {
          using: effectiveRequest.using || null,
          algorithm: effectiveRequest.algorithm || 'UMAP',
        },
      });
    } catch (err: any) {
      setError(err?.message || 'Visualization failed');
      setLoading(false);
    }
  };

  const normalized = useMemo(() => normalizeCoordinates(reduced), [reduced]);
  const colors = useMemo(() => colorBy(points, visualizeRequest || DEFAULT_REQUEST), [points, visualizeRequest]);
  const activePoint = activeIndex != null ? points[activeIndex] : null;

  useEffect(() => {
    setSelectedPoint(activePoint);
  }, [activePoint, setSelectedPoint]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-3">
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 xl:grid-cols-12">
        <div className="min-h-0 rounded border border-border-light bg-white xl:col-span-8">
          <div className="border-b border-border-light px-3 py-2 text-xs font-semibold text-text-main">Scatter Plot</div>
          <div className="h-[calc(100%-33px)] overflow-hidden p-2">
            {error && <ErrorState message={error} />}
            {!error && normalized.length === 0 && !loading && <EmptyState title="Run a visualization request" />}
            {!error && loading && (
              <div className="flex h-full items-center justify-center text-xs text-text-sub">Reducing dimensions...</div>
            )}
            {!error && normalized.length > 0 && (
              <svg viewBox="0 0 1000 600" className="h-full w-full rounded border border-border-light bg-surface-light">
                {normalized.map((point, index) => (
                  <circle
                    key={`${String(points[index]?.id)}-${index}`}
                    cx={point.x}
                    cy={point.y}
                    r={activeIndex === index ? 6 : 4}
                    fill={activeIndex === index ? '#111827' : colors[index]}
                    opacity={activeIndex === index ? 0.95 : 0.8}
                    onMouseEnter={() => setActiveIndex(index)}
                  />
                ))}
              </svg>
            )}
          </div>
        </div>

        <div className="min-h-0 flex flex-col gap-3 xl:col-span-4">
          <div className="min-h-0 flex-1 rounded border border-border-light bg-white">
            <div className="flex items-center justify-between border-b border-border-light px-3 py-2">
              <div className="text-xs font-semibold text-text-main">Request Editor</div>
              <button
                type="button"
                onClick={() => setRequestInput(safeJson(DEFAULT_REQUEST))}
                className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
              >
                <RefreshCw size={12} />
                Reset
              </button>
            </div>
            <div className="space-y-2 p-2">
              <textarea
                value={requestInput}
                onChange={(event) => setRequestInput(event.target.value)}
                className="h-52 w-full resize-none rounded border border-border-light p-2 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-primary/35"
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    try {
                      const parsed = JSON.parse(requestInput) as VisualizeRequest;
                      const normalizedRequest: VisualizeRequest = {
                        limit: parsed.limit || 300,
                        using: parsed.using || null,
                        filter: parsed.filter || null,
                        color_by: parsed.color_by || null,
                        algorithm: parsed.algorithm || 'UMAP',
                      };
                      const effective = normalizeRequestUsing(normalizedRequest);
                      setVisualizeRequest(effective);
                      runRequest(effective);
                    } catch {
                      setError('Invalid JSON in request editor');
                    }
                  }}
                  className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
                >
                  <Play size={12} />
                  Run
                </button>
                <button
                  type="button"
                  onClick={() => navigator.clipboard.writeText(requestInput)}
                  className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs hover:bg-surface-light"
                >
                  <Copy size={12} />
                  Copy
                </button>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 rounded border border-border-light bg-white">
            <div className="border-b border-border-light px-3 py-2 text-xs font-semibold text-text-main">Data Panel</div>
            <pre className="h-[calc(100%-33px)] overflow-auto p-2 text-[11px] text-text-main">
              {activePoint ? safeJson(activePoint) : 'Hover a point to preview payload and vectors'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VisualizeTab;
