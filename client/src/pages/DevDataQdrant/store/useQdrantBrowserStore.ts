import { create } from 'zustand';
import { GraphRequest, ParsedFilter, PointId, PointRecord, QdrantTabKey, VisualizeRequest } from '../types';

const DEFAULT_VISUALIZE_REQUEST: VisualizeRequest = {
  limit: 300,
  algorithm: 'UMAP',
};

const DEFAULT_GRAPH_REQUEST: GraphRequest = {
  limit: 5,
  tree: false,
};

interface QdrantBrowserState {
  selectedCollection: string | null;
  activeTab: QdrantTabKey;
  similarIds: PointId[];
  payloadFilters: ParsedFilter[];
  usingVector: string | null;
  similarityLimit: number;
  selectedPoint: PointRecord | null;
  visualizeRequest: VisualizeRequest;
  graphRequest: GraphRequest;
  graphSeedPoint: PointRecord | null;

  setSelectedCollection: (collection: string | null) => void;
  setActiveTab: (tab: QdrantTabKey) => void;
  setSimilarIds: (ids: PointId[]) => void;
  setPayloadFilters: (filters: ParsedFilter[]) => void;
  setUsingVector: (usingVector: string | null) => void;
  resetPointsQuery: () => void;
  increaseSimilarityLimit: (size: number) => void;
  setSelectedPoint: (point: PointRecord | null) => void;
  setVisualizeRequest: (request: VisualizeRequest) => void;
  setGraphRequest: (request: GraphRequest) => void;
  setGraphSeedPoint: (point: PointRecord | null) => void;
  hydrateFromUrl: (tab: QdrantTabKey | null, collection: string | null) => void;
}

export const useQdrantBrowserStore = create<QdrantBrowserState>((set) => ({
  selectedCollection: null,
  activeTab: 'points',
  similarIds: [],
  payloadFilters: [],
  usingVector: null,
  similarityLimit: 20,
  selectedPoint: null,
  visualizeRequest: DEFAULT_VISUALIZE_REQUEST,
  graphRequest: DEFAULT_GRAPH_REQUEST,
  graphSeedPoint: null,

  setSelectedCollection: (collection) =>
    set({
      selectedCollection: collection,
      similarIds: [],
      payloadFilters: [],
      usingVector: null,
      similarityLimit: 20,
      selectedPoint: null,
      graphSeedPoint: null,
    }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setSimilarIds: (ids) => set({ similarIds: ids, similarityLimit: 20 }),
  setPayloadFilters: (filters) => set({ payloadFilters: filters, similarityLimit: 20 }),
  setUsingVector: (usingVector) => set({ usingVector, similarityLimit: 20 }),
  resetPointsQuery: () =>
    set({
      similarIds: [],
      payloadFilters: [],
      usingVector: null,
      similarityLimit: 20,
      selectedPoint: null,
    }),
  increaseSimilarityLimit: (size) =>
    set((state) => ({ similarityLimit: Math.max(1, state.similarityLimit + Math.max(size, 1)) })),
  setSelectedPoint: (point) => set({ selectedPoint: point }),
  setVisualizeRequest: (request) => set({ visualizeRequest: request }),
  setGraphRequest: (request) => set({ graphRequest: request }),
  setGraphSeedPoint: (point) => set({ graphSeedPoint: point }),
  hydrateFromUrl: (tab, collection) =>
    set((state) => ({
      activeTab: tab || state.activeTab,
      selectedCollection: collection || state.selectedCollection,
    })),
}));

