import { appConfig } from '../../../config/appConfig';
import {
  AliasListResponse,
  CollectionClusterResponse,
  CollectionInfoResponse,
  CollectionListResponse,
  CollectionSummaryResponse,
  FacetResponse,
  MatrixPairsResponse,
  OptimizationsResponse,
  PayloadQualityResponse,
  QueryPointsResponse,
  RetrievePointsResponse,
  ScrollPointsResponse,
  SnapshotListResponse,
  ClusterStatusResponse,
  StandardApiError,
  VectorHealthResponse,
} from '../types';

type HttpMethod = 'GET' | 'POST';

interface RequestOptions {
  token: string;
  method?: HttpMethod;
  body?: Record<string, unknown>;
}

export class QdrantBrowserApiError extends Error {
  status: number;
  payload?: StandardApiError;

  constructor(message: string, status: number, payload?: StandardApiError) {
    super(message);
    this.name = 'QdrantBrowserApiError';
    this.status = status;
    this.payload = payload;
  }
}

const API_BASE = `${appConfig.api.baseUrl}/api/v2/devdata/qdrant`;

async function parseError(response: Response): Promise<QdrantBrowserApiError> {
  let parsed: any = null;
  try {
    parsed = await response.json();
  } catch {
    parsed = null;
  }

  const payload: StandardApiError | undefined =
    parsed && typeof parsed === 'object'
      ? (parsed.detail && typeof parsed.detail === 'object' ? parsed.detail : parsed)
      : undefined;
  const message = payload?.message || payload?.code || `Request failed with status ${response.status}`;

  return new QdrantBrowserApiError(message, response.status, payload);
}

async function qdrantRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const { token, method = 'GET', body } = options;
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'X-MS-TOKEN-AAD': token,
      ...(method === 'POST' ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(method === 'POST' ? { body: JSON.stringify(body || {}) } : {}),
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  return (await response.json()) as T;
}

function parseFilename(contentDisposition: string | null, fallbackName: string): string {
  if (!contentDisposition) {
    return fallbackName;
  }

  const match = contentDisposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)"?/i);
  if (!match || !match[1]) {
    return fallbackName;
  }

  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

export const qdrantBrowserApi = {
  listCollections(token: string): Promise<CollectionListResponse> {
    return qdrantRequest<CollectionListResponse>('/collections', { token });
  },

  getCollection(token: string, collectionName: string): Promise<CollectionInfoResponse> {
    return qdrantRequest<CollectionInfoResponse>(`/collections/${encodeURIComponent(collectionName)}`, { token });
  },

  getCollectionSummary(token: string, collectionName: string): Promise<CollectionSummaryResponse> {
    return qdrantRequest<CollectionSummaryResponse>(`/collections/${encodeURIComponent(collectionName)}/summary`, {
      token,
    });
  },

  scrollPoints(token: string, collectionName: string, body: Record<string, unknown>): Promise<ScrollPointsResponse> {
    return qdrantRequest<ScrollPointsResponse>(
      `/collections/${encodeURIComponent(collectionName)}/points/scroll`,
      {
        token,
        method: 'POST',
        body,
      }
    );
  },

  queryPoints(token: string, collectionName: string, body: Record<string, unknown>): Promise<QueryPointsResponse> {
    return qdrantRequest<QueryPointsResponse>(
      `/collections/${encodeURIComponent(collectionName)}/points/query`,
      {
        token,
        method: 'POST',
        body,
      }
    );
  },

  retrievePoints(
    token: string,
    collectionName: string,
    body: Record<string, unknown>
  ): Promise<RetrievePointsResponse> {
    return qdrantRequest<RetrievePointsResponse>(
      `/collections/${encodeURIComponent(collectionName)}/points/retrieve`,
      {
        token,
        method: 'POST',
        body,
      }
    );
  },

  facet(token: string, collectionName: string, body: Record<string, unknown>): Promise<FacetResponse> {
    return qdrantRequest<FacetResponse>(`/collections/${encodeURIComponent(collectionName)}/facet`, {
      token,
      method: 'POST',
      body,
    });
  },

  getAliases(token: string, collectionName: string): Promise<AliasListResponse> {
    return qdrantRequest<AliasListResponse>(`/collections/${encodeURIComponent(collectionName)}/aliases`, { token });
  },

  getSnapshots(token: string, collectionName: string): Promise<SnapshotListResponse> {
    return qdrantRequest<SnapshotListResponse>(`/collections/${encodeURIComponent(collectionName)}/snapshots`, {
      token,
    });
  },

  async downloadSnapshot(
    token: string,
    collectionName: string,
    snapshotName: string,
    onProgress?: (loaded: number, total: number) => void
  ): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch(
      `${API_BASE}/collections/${encodeURIComponent(collectionName)}/snapshots/${encodeURIComponent(
        snapshotName
      )}/download`,
      {
        headers: {
          'X-MS-TOKEN-AAD': token,
        },
      }
    );

    if (!response.ok) {
      throw await parseError(response);
    }

    const total = Number(response.headers.get('content-length') || 0);
    const contentDisposition = response.headers.get('content-disposition');
    const filename = parseFilename(contentDisposition, snapshotName);

    if (!response.body) {
      const blob = await response.blob();
      return { blob, filename };
    }

    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let loaded = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      if (!value) {
        continue;
      }
      chunks.push(value);
      loaded += value.length;
      if (onProgress) {
        onProgress(loaded, total);
      }
    }

    return {
      blob: new Blob(chunks),
      filename,
    };
  },

  getCluster(token: string): Promise<ClusterStatusResponse> {
    return qdrantRequest<ClusterStatusResponse>('/cluster', { token });
  },

  getCollectionCluster(token: string, collectionName: string): Promise<CollectionClusterResponse> {
    return qdrantRequest<CollectionClusterResponse>(`/collections/${encodeURIComponent(collectionName)}/cluster`, {
      token,
    });
  },

  getOptimizations(token: string, collectionName: string): Promise<OptimizationsResponse> {
    return qdrantRequest<OptimizationsResponse>(
      `/collections/${encodeURIComponent(collectionName)}/optimizations`,
      {
        token,
      }
    );
  },

  getPayloadQuality(
    token: string,
    collectionName: string,
    body: Record<string, unknown>
  ): Promise<PayloadQualityResponse> {
    return qdrantRequest<PayloadQualityResponse>(
      `/collections/${encodeURIComponent(collectionName)}/insights/payload`,
      {
        token,
        method: 'POST',
        body,
      }
    );
  },

  getVectorHealth(
    token: string,
    collectionName: string,
    body: Record<string, unknown>
  ): Promise<VectorHealthResponse> {
    return qdrantRequest<VectorHealthResponse>(
      `/collections/${encodeURIComponent(collectionName)}/insights/vectors`,
      {
        token,
        method: 'POST',
        body,
      }
    );
  },

  matrixPairs(
    token: string,
    collectionName: string,
    body: Record<string, unknown>
  ): Promise<MatrixPairsResponse> {
    return qdrantRequest<MatrixPairsResponse>(
      `/collections/${encodeURIComponent(collectionName)}/points/search/matrix/pairs`,
      {
        token,
        method: 'POST',
        body,
      }
    );
  },
};
