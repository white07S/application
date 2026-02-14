import React, { useEffect, useMemo, useState } from 'react';
import { Circle, RefreshCw } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { qdrantBrowserApi } from '../../api/qdrantBrowserApi';
import { ClusterStatusResponse, CollectionClusterResponse } from '../../types';
import EmptyState from '../EmptyState';
import ErrorState from '../ErrorState';

interface ClusterTabProps {
  collectionName: string;
}

const ClusterTab: React.FC<ClusterTabProps> = ({ collectionName }) => {
  const { getApiAccessToken } = useAuth();
  const [cluster, setCluster] = useState<ClusterStatusResponse | null>(null);
  const [collectionCluster, setCollectionCluster] = useState<CollectionClusterResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }
      const [clusterResponse, collectionClusterResponse] = await Promise.all([
        qdrantBrowserApi.getCluster(token),
        qdrantBrowserApi.getCollectionCluster(token, collectionName),
      ]);

      setCluster(clusterResponse);
      setCollectionCluster(collectionClusterResponse);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch cluster data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionName]);

  const shards = useMemo(() => {
    if (!collectionCluster) {
      return [];
    }
    const local = Array.isArray(collectionCluster.local_shards) ? collectionCluster.local_shards : [];
    const remote = Array.isArray(collectionCluster.remote_shards) ? collectionCluster.remote_shards : [];
    return [...local, ...remote];
  }, [collectionCluster]);

  const peerIds = useMemo(() => {
    const peers = cluster?.peers || {};
    return Object.keys(peers).sort((a, b) => Number(a) - Number(b));
  }, [cluster?.peers]);

  const clusterEnabled = cluster?.status === 'enabled';

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-3">
      <div className="rounded border border-border-light bg-white">
        <div className="flex items-center justify-between border-b border-border-light px-3 py-2">
          <div className="text-xs font-semibold text-text-main">Cluster Monitor</div>
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

        {error && <div className="p-2"><ErrorState message={error} onRetry={refresh} /></div>}

        {!clusterEnabled ? (
          <div className="p-3">
            <div className="rounded border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
              Distributed mode is not enabled for this cluster. Collection-level shard snapshot is shown below.
            </div>
            {collectionCluster ? (
              <div className="mt-2">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-text-sub">
                      <th className="px-2 py-1 font-medium">Shard</th>
                      <th className="px-2 py-1 font-medium">State</th>
                      <th className="px-2 py-1 font-medium">Location</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shards.map((shard, index) => (
                      <tr key={`${shard.shard_id || index}-${shard.peer_id || 'local'}`} className="border-t border-border-light">
                        <td className="px-2 py-1 font-mono text-text-main">{String(shard.shard_id ?? '-')}</td>
                        <td className="px-2 py-1 text-text-sub">{String(shard.state ?? 'unknown')}</td>
                        <td className="px-2 py-1 text-text-sub">
                          {shard.peer_id ? `Remote (${shard.peer_id})` : 'Local'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="mt-2">
                <EmptyState title="No collection cluster data" />
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3 p-3">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
              <div className="rounded border border-border-light bg-surface-light px-2 py-1">
                <div className="text-[10px] uppercase text-text-sub">Cluster status</div>
                <div className="flex items-center gap-1 text-xs font-medium text-green-700">
                  <Circle size={10} fill="currentColor" />
                  enabled
                </div>
              </div>
              <div className="rounded border border-border-light bg-surface-light px-2 py-1">
                <div className="text-[10px] uppercase text-text-sub">Peers</div>
                <div className="text-xs font-medium text-text-main">{peerIds.length}</div>
              </div>
              <div className="rounded border border-border-light bg-surface-light px-2 py-1">
                <div className="text-[10px] uppercase text-text-sub">Shards</div>
                <div className="text-xs font-medium text-text-main">{shards.length}</div>
              </div>
              <div className="rounded border border-border-light bg-surface-light px-2 py-1">
                <div className="text-[10px] uppercase text-text-sub">Transfers</div>
                <div className="text-xs font-medium text-text-main">
                  {Array.isArray(collectionCluster?.result?.shard_transfers)
                    ? collectionCluster?.result?.shard_transfers.length
                    : 0}
                </div>
              </div>
              <div className="rounded border border-border-light bg-surface-light px-2 py-1">
                <div className="text-[10px] uppercase text-text-sub">Resharding ops</div>
                <div className="text-xs font-medium text-text-main">
                  {Array.isArray(collectionCluster?.result?.resharding_operations)
                    ? collectionCluster?.result?.resharding_operations.length
                    : 0}
                </div>
              </div>
            </div>

            <div className="max-h-[calc(100vh-360px)] overflow-auto rounded border border-border-light">
              <table className="w-full min-w-[720px] text-xs">
                <thead>
                  <tr className="bg-surface-light text-left text-text-sub">
                    <th className="px-2 py-1 font-medium">Shard</th>
                    <th className="px-2 py-1 font-medium">State</th>
                    <th className="px-2 py-1 font-medium">Peer</th>
                    <th className="px-2 py-1 font-medium">Points</th>
                    <th className="px-2 py-1 font-medium">Shard Key</th>
                    <th className="px-2 py-1 font-medium">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {shards.map((shard, index) => (
                    <tr key={`${shard.shard_id || index}-${shard.peer_id || 'local'}`} className="border-t border-border-light">
                      <td className="px-2 py-1 font-mono text-text-main">{String(shard.shard_id ?? '-')}</td>
                      <td className="px-2 py-1 text-text-sub">{String(shard.state ?? 'unknown')}</td>
                      <td className="px-2 py-1 text-text-sub">{String(shard.peer_id ?? collectionCluster?.result?.peer_id ?? '-')}</td>
                      <td className="px-2 py-1 text-text-sub">{String(shard.points_count ?? '-')}</td>
                      <td className="px-2 py-1 text-text-sub">{String(shard.shard_key ?? '-')}</td>
                      <td className="px-2 py-1 text-text-sub">{shard.peer_id ? 'Remote' : 'Local'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ClusterTab;

