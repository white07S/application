import { qdrantBrowserApi } from '../api/qdrantBrowserApi';
import { PointId, SearchQualityRequest } from '../types';

export interface PrecisionResult {
  precision: number;
  exactIds: PointId[];
  approxIds: PointId[];
  exactElapsedMs: number;
  approxElapsedMs: number;
}

function round(value: number, decimals = 4): number {
  const factor = 10 ** decimals;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

export function summarizePrecisions(values: number[]): { mean: number; stdDev: number } {
  if (values.length === 0) {
    return { mean: 0, stdDev: 0 };
  }

  const mean = values.reduce((sum, current) => sum + current, 0) / values.length;
  const variance = values.reduce((sum, current) => sum + (current - mean) ** 2, 0) / values.length;
  return { mean: round(mean), stdDev: round(Math.sqrt(variance)) };
}

export function normalizeVectorConfig(collectionInfo: Record<string, any>): Record<string, { size?: number; distance?: string }> {
  const vectors = collectionInfo?.config?.params?.vectors;
  if (!vectors) {
    return {};
  }

  // Unnamed vector
  if (typeof vectors === 'object' && 'size' in vectors && 'distance' in vectors) {
    return {
      default: {
        size: Number(vectors.size) || undefined,
        distance: typeof vectors.distance === 'string' ? vectors.distance : undefined,
      },
    };
  }

  if (typeof vectors !== 'object') {
    return {};
  }

  const normalized: Record<string, { size?: number; distance?: string }> = {};
  Object.entries(vectors).forEach(([name, config]) => {
    if (!config || typeof config !== 'object') {
      normalized[name] = {};
      return;
    }
    const typedConfig = config as Record<string, unknown>;
    normalized[name] = {
      size: typeof typedConfig.size === 'number' ? typedConfig.size : undefined,
      distance: typeof typedConfig.distance === 'string' ? typedConfig.distance : undefined,
    };
  });

  return normalized;
}

export async function checkIndexPrecision(
  token: string,
  collectionName: string,
  pointId: PointId,
  request: SearchQualityRequest
): Promise<PrecisionResult> {
  const { using = null, limit, filter = null, params = null, timeout = 20 } = request;

  const exactStart = Date.now();
  const exact = await qdrantBrowserApi.queryPoints(token, collectionName, {
    query: pointId,
    limit,
    with_payload: false,
    with_vector: false,
    using: using || undefined,
    filter: filter || undefined,
    timeout,
    params: { exact: true },
  });
  const exactElapsedMs = Date.now() - exactStart;

  const approxStart = Date.now();
  const approx = await qdrantBrowserApi.queryPoints(token, collectionName, {
    query: pointId,
    limit,
    with_payload: false,
    with_vector: false,
    using: using || undefined,
    filter: filter || undefined,
    timeout,
    params: params || undefined,
  });
  const approxElapsedMs = Date.now() - approxStart;

  const exactIds = exact.points.map((item) => item.id);
  const approxIds = approx.points.map((item) => item.id);
  const overlap = exactIds.filter((id) => approxIds.includes(id));
  const precision = exactIds.length === 0 ? 0 : overlap.length / exactIds.length;

  return {
    precision,
    exactIds,
    approxIds,
    exactElapsedMs,
    approxElapsedMs,
  };
}

