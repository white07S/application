export type PointId = string | number;

export type QdrantTabKey =
  | 'points'
  | 'info'
  | 'quality'
  | 'data_quality'
  | 'vector_health'
  | 'snapshots'
  | 'cluster'
  | 'optimizations'
  | 'visualize'
  | 'graph';

export interface StandardApiError {
  code: string;
  message: string;
  status: number;
  details?: Record<string, unknown>;
}

export interface CollectionListItem {
  name: string;
  status?: string;
  points_count?: number;
  vectors_count?: number;
}

export interface CollectionListResponse {
  collections: CollectionListItem[];
}

export interface PayloadSchemaEntry {
  data_type?: string;
  points?: number;
  [key: string]: unknown;
}

export interface CollectionInfoResponse {
  collection_name: string;
  status?: string;
  points_count: number;
  vectors_count: number;
  named_vectors: string[];
  payload_schema: Record<string, PayloadSchemaEntry>;
  info: Record<string, any>;
}

export interface CollectionSummaryResponse {
  collection_name: string;
  status?: string;
  points_count: number;
  vectors_count: number;
  vectors: string[];
  aliases_count: number;
  snapshots_count: number;
}

export interface PointRecord {
  id: PointId;
  payload?: Record<string, any>;
  vector?: any;
  score?: number;
  [key: string]: any;
}

export interface ScrollPointsResponse {
  points: PointRecord[];
  next_page_offset: PointId | null;
  total_loaded: number;
}

export interface QueryPointsResponse {
  points: PointRecord[];
  total_loaded: number;
}

export interface RetrievePointsResponse {
  points: PointRecord[];
  total_loaded: number;
}

export interface FacetHit {
  value: string | number | boolean | null;
  count?: number;
  [key: string]: unknown;
}

export interface FacetResponse {
  hits: FacetHit[];
}

export interface AliasItem {
  alias_name: string;
  collection_name?: string;
}

export interface AliasListResponse {
  aliases: AliasItem[];
}

export interface SnapshotListItem {
  name: string;
  creation_time?: string;
  size?: number;
  [key: string]: unknown;
}

export interface SnapshotListResponse {
  snapshots: SnapshotListItem[];
}

export interface ClusterStatusResponse {
  status: string;
  peers: Record<string, any>;
  details: Record<string, any>;
}

export interface CollectionClusterResponse {
  status: string;
  result: Record<string, any>;
  local_shards: Record<string, any>[];
  remote_shards: Record<string, any>[];
}

export interface OptimizationsResponse {
  result: Record<string, any>;
}

export interface MatrixPair {
  a: PointId;
  b: PointId;
  score?: number;
  [key: string]: unknown;
}

export interface MatrixPairsResponse {
  pairs: MatrixPair[];
}

export interface TopFieldValue {
  value: string | number | boolean | null;
  count: number;
  pct: number;
}

export interface PayloadFieldQuality {
  field: string;
  coverage_pct: number;
  null_pct: number;
  empty_pct: number;
  distinct_count: number;
  top_values: TopFieldValue[];
  type_conflicts: string[];
}

export interface PayloadQualityResponse {
  sample_points: number;
  fields: PayloadFieldQuality[];
}

export interface VectorNormPercentiles {
  p05: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  p95: number | null;
}

export interface VectorHealthEntry {
  vector_name: string;
  expected_dim: number | null;
  points_seen: number;
  present_count: number;
  missing_rate_pct: number;
  dimension_mismatch_count: number;
  unsupported_format_count: number;
  zero_vector_rate_pct: number;
  norm_percentiles: VectorNormPercentiles;
}

export interface VectorHealthResponse {
  sample_points: number;
  vectors: VectorHealthEntry[];
}

export interface ParsedFilter {
  key: string;
  value: string | number | boolean | null;
  isIdFilter?: boolean;
}

export interface VectorConfig {
  size?: number;
  distance?: string;
}

export interface SearchQualityRequest {
  limit: number;
  using?: string | null;
  filter?: Record<string, any> | null;
  params?: Record<string, any> | null;
  timeout?: number;
}

export interface VisualizeRequest {
  limit: number;
  using?: string | null;
  filter?: Record<string, any> | null;
  color_by?: string | { payload?: string; query?: unknown } | null;
  algorithm?: 'TSNE' | 'UMAP' | 'PCA';
}

export interface GraphRequest {
  limit: number;
  using?: string | null;
  filter?: Record<string, any> | null;
  sample?: number | null;
  tree?: boolean;
}
