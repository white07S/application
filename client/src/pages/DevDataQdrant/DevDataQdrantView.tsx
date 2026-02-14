import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/useAuth';
import { qdrantBrowserApi } from './api/qdrantBrowserApi';
import CollectionSelector from './components/CollectionSelector';
import QdrantTabNav from './components/QdrantTabNav';
import QdrantStatusBar from './components/QdrantStatusBar';
import ErrorState from './components/ErrorState';
import EmptyState from './components/EmptyState';
import PointsTab from './components/tabs/PointsTab';
import InfoTab from './components/tabs/InfoTab';
import SearchQualityTab from './components/tabs/SearchQualityTab';
import DataQualityTab from './components/tabs/DataQualityTab';
import VectorHealthTab from './components/tabs/VectorHealthTab';
import SnapshotsTab from './components/tabs/SnapshotsTab';
import ClusterTab from './components/tabs/ClusterTab';
import OptimizationsTab from './components/tabs/OptimizationsTab';
import VisualizeTab from './components/tabs/VisualizeTab';
import GraphTab from './components/tabs/GraphTab';
import { useQdrantBrowserStore } from './store/useQdrantBrowserStore';
import { CollectionInfoResponse, CollectionListItem, CollectionSummaryResponse, PointRecord, QdrantTabKey } from './types';

const VALID_TABS: QdrantTabKey[] = [
  'points',
  'info',
  'quality',
  'data_quality',
  'vector_health',
  'snapshots',
  'cluster',
  'optimizations',
  'visualize',
  'graph',
];

function parseTab(value: string | null): QdrantTabKey {
  if (!value) {
    return 'points';
  }
  return VALID_TABS.includes(value as QdrantTabKey) ? (value as QdrantTabKey) : 'points';
}

const DevDataQdrantView: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { getApiAccessToken } = useAuth();
  const {
    selectedCollection,
    activeTab,
    setSelectedCollection,
    setActiveTab,
    setGraphRequest,
    setGraphSeedPoint,
  } = useQdrantBrowserStore();

  const [collections, setCollections] = useState<CollectionListItem[]>([]);
  const [collectionInfo, setCollectionInfo] = useState<CollectionInfoResponse | null>(null);
  const [collectionSummary, setCollectionSummary] = useState<CollectionSummaryResponse | null>(null);
  const [loadingCollections, setLoadingCollections] = useState(false);
  const [loadingCollectionData, setLoadingCollectionData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const collectionSet = useMemo(() => new Set(collections.map((item) => item.name)), [collections]);
  const syncingFromUrlRef = useRef(false);

  const refreshCollections = async () => {
    setLoadingCollections(true);
    setError(null);
    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }

      const listResponse = await qdrantBrowserApi.listCollections(token);
      const items = listResponse.collections || [];
      setCollections(items);

      if (items.length === 0) {
        setSelectedCollection(null);
        setCollectionInfo(null);
        setCollectionSummary(null);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load collections');
    } finally {
      setLoadingCollections(false);
    }
  };

  const refreshCollectionData = async (collectionName: string) => {
    setLoadingCollectionData(true);
    setError(null);
    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }
      const [info, summary] = await Promise.all([
        qdrantBrowserApi.getCollection(token, collectionName),
        qdrantBrowserApi.getCollectionSummary(token, collectionName),
      ]);
      setCollectionInfo(info);
      setCollectionSummary(summary);
      setLastRefresh(new Date());
    } catch (err: any) {
      setError(err?.message || 'Failed to load collection data');
    } finally {
      setLoadingCollectionData(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const queryTab = parseTab(params.get('qtab'));
    const queryCollection = params.get('collection');
    const state = useQdrantBrowserStore.getState();
    const currentActiveTab = state.activeTab;
    const currentSelectedCollection = state.selectedCollection;
    let synced = false;

    if (currentActiveTab !== queryTab) {
      setActiveTab(queryTab);
      synced = true;
    }

    if (collections.length === 0) {
      if (currentSelectedCollection !== null) {
        setSelectedCollection(null);
        synced = true;
      }
      syncingFromUrlRef.current = synced;
      return;
    }

    if (queryCollection && collectionSet.has(queryCollection)) {
      if (currentSelectedCollection !== queryCollection) {
        setSelectedCollection(queryCollection);
        synced = true;
      }
      syncingFromUrlRef.current = synced;
      return;
    }

    const selectedIsValid = currentSelectedCollection ? collectionSet.has(currentSelectedCollection) : false;
    if (!selectedIsValid) {
      const fallback = collections[0]?.name || null;
      if (currentSelectedCollection !== fallback) {
        setSelectedCollection(fallback);
        synced = true;
      }
    }
    syncingFromUrlRef.current = synced;
  }, [collectionSet, collections, location.search, setActiveTab, setSelectedCollection]);

  useEffect(() => {
    refreshCollections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedCollection) {
      return;
    }
    refreshCollectionData(selectedCollection);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCollection]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const currentCollection = params.get('collection');
    const currentTab = parseTab(params.get('qtab'));
    const currentCollectionNormalized = currentCollection || null;
    const selectedCollectionNormalized = selectedCollection || null;

    if (syncingFromUrlRef.current) {
      const tabAligned = currentTab === activeTab;
      const collectionAligned = currentCollectionNormalized === selectedCollectionNormalized;
      if (!tabAligned || !collectionAligned) {
        return;
      }
      syncingFromUrlRef.current = false;
    }

    let hasChanged = false;
    if (selectedCollection && currentCollection !== selectedCollection) {
      params.set('collection', selectedCollection);
      hasChanged = true;
    }
    if (currentTab !== activeTab) {
      params.set('qtab', activeTab);
      hasChanged = true;
    }
    if (!selectedCollection && currentCollection) {
      params.delete('collection');
      hasChanged = true;
    }

    if (hasChanged) {
      navigate(`${location.pathname}?${params.toString()}`, { replace: true });
    }
  }, [activeTab, collectionSet, location.pathname, location.search, navigate, selectedCollection]);

  const body = useMemo(() => {
    if (!selectedCollection) {
      return <EmptyState title="No Qdrant collections available" description="Create collections in Qdrant and refresh." />;
    }

    switch (activeTab) {
      case 'points':
        return (
          <PointsTab
            collectionName={selectedCollection}
            collectionInfo={collectionInfo}
            onOpenGraph={(point: PointRecord, vectorName: string | null) => {
              setGraphSeedPoint(point);
              setGraphRequest({
                limit: 5,
                using: vectorName || null,
                tree: false,
              });
              setActiveTab('graph');
            }}
          />
        );
      case 'info':
        return <InfoTab collectionName={selectedCollection} collectionInfo={collectionInfo} />;
      case 'quality':
        return <SearchQualityTab collectionName={selectedCollection} collectionInfo={collectionInfo} />;
      case 'data_quality':
        return <DataQualityTab collectionName={selectedCollection} collectionInfo={collectionInfo} />;
      case 'vector_health':
        return <VectorHealthTab collectionName={selectedCollection} collectionInfo={collectionInfo} />;
      case 'snapshots':
        return <SnapshotsTab collectionName={selectedCollection} />;
      case 'cluster':
        return <ClusterTab collectionName={selectedCollection} />;
      case 'optimizations':
        return <OptimizationsTab collectionName={selectedCollection} />;
      case 'visualize':
        return <VisualizeTab collectionName={selectedCollection} collectionInfo={collectionInfo} />;
      case 'graph':
        return <GraphTab collectionName={selectedCollection} />;
      default:
        return <EmptyState title="Unknown tab" />;
    }
  }, [
    activeTab,
    collectionInfo,
    selectedCollection,
    setActiveTab,
    setGraphRequest,
    setGraphSeedPoint,
  ]);

  return (
    <div className="flex h-[calc(100vh-9.5rem)] min-h-[620px] flex-col overflow-hidden rounded border border-border-light bg-surface-light">
      <div className="flex items-center gap-2 border-b border-border-light bg-white px-3 py-2">
        <CollectionSelector
          collections={collections}
          value={selectedCollection}
          loading={loadingCollections}
          onChange={setSelectedCollection}
        />
      </div>

      <QdrantStatusBar
        summary={collectionSummary}
        loading={loadingCollectionData}
        collectionName={selectedCollection}
        onRefresh={() => {
          if (selectedCollection) {
            refreshCollectionData(selectedCollection);
          }
        }}
        lastRefresh={lastRefresh}
      />

      <QdrantTabNav activeTab={activeTab} onChange={setActiveTab} />

      {error && (
        <div className="p-2">
          <ErrorState message={error} onRetry={refreshCollections} />
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-hidden">
        {loadingCollections && collections.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-text-sub">Loading collections...</div>
        ) : (
          body
        )}
      </div>
    </div>
  );
};

export default DevDataQdrantView;
