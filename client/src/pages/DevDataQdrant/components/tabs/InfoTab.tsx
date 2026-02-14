import React, { useEffect, useMemo, useState } from 'react';
import { Copy, RefreshCw } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { qdrantBrowserApi } from '../../api/qdrantBrowserApi';
import { AliasItem, CollectionClusterResponse, CollectionInfoResponse } from '../../types';
import ErrorState from '../ErrorState';
import EmptyState from '../EmptyState';
import { safeJson } from '../../utils/formatters';

interface InfoTabProps {
  collectionName: string;
  collectionInfo: CollectionInfoResponse | null;
}

const InfoTab: React.FC<InfoTabProps> = ({ collectionName, collectionInfo }) => {
  const { getApiAccessToken } = useAuth();
  const [aliases, setAliases] = useState<AliasItem[]>([]);
  const [cluster, setCluster] = useState<CollectionClusterResponse | null>(null);
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
      const [aliasResponse, clusterResponse] = await Promise.all([
        qdrantBrowserApi.getAliases(token, collectionName),
        qdrantBrowserApi.getCollectionCluster(token, collectionName),
      ]);
      setAliases(aliasResponse.aliases || []);
      setCluster(clusterResponse);
    } catch (err: any) {
      setError(err?.message || 'Failed to load collection details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionName]);

  const shardRows = useMemo(() => {
    if (!cluster) {
      return [];
    }
    const localShards = Array.isArray(cluster.local_shards) ? cluster.local_shards : [];
    const remoteShards = Array.isArray(cluster.remote_shards) ? cluster.remote_shards : [];
    return [...localShards, ...remoteShards];
  }, [cluster]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto p-3">
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="rounded border border-border-light bg-white">
          <div className="flex items-center justify-between border-b border-border-light px-3 py-2">
            <div className="text-xs font-semibold text-text-main">Aliases</div>
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
          <div className="max-h-[220px] overflow-auto p-2">
            {aliases.length === 0 ? (
              <EmptyState title="No aliases configured" />
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-text-sub">
                    <th className="px-2 py-1 font-medium">Alias</th>
                    <th className="px-2 py-1 font-medium">Collection</th>
                  </tr>
                </thead>
                <tbody>
                  {aliases.map((alias) => (
                    <tr key={`${alias.alias_name}-${alias.collection_name || ''}`} className="border-t border-border-light">
                      <td className="px-2 py-1 font-mono text-text-main">{alias.alias_name}</td>
                      <td className="px-2 py-1 text-text-sub">{alias.collection_name || collectionName}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="rounded border border-border-light bg-white">
          <div className="flex items-center justify-between border-b border-border-light px-3 py-2">
            <div className="text-xs font-semibold text-text-main">Cluster Shards</div>
            <div className="text-[10px] text-text-sub uppercase">{cluster?.status || 'unknown'}</div>
          </div>
          <div className="max-h-[220px] overflow-auto p-2">
            {!cluster ? (
              <EmptyState title="Cluster data unavailable" />
            ) : shardRows.length === 0 ? (
              <EmptyState title="No shard information" />
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-text-sub">
                    <th className="px-2 py-1 font-medium">Shard</th>
                    <th className="px-2 py-1 font-medium">State</th>
                    <th className="px-2 py-1 font-medium">Location</th>
                    <th className="px-2 py-1 font-medium">Key</th>
                  </tr>
                </thead>
                <tbody>
                  {shardRows.map((shard, index) => (
                    <tr key={`${shard.shard_id || index}-${shard.peer_id || 'local'}`} className="border-t border-border-light">
                      <td className="px-2 py-1 font-mono text-text-main">{String(shard.shard_id ?? '-')}</td>
                      <td className="px-2 py-1 text-text-sub">{String(shard.state ?? 'unknown')}</td>
                      <td className="px-2 py-1 text-text-sub">
                        {shard.peer_id ? `Remote (${shard.peer_id})` : `Local (${cluster?.result?.peer_id ?? 'self'})`}
                      </td>
                      <td className="px-2 py-1 text-text-sub">{String(shard.shard_key ?? '-')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 rounded border border-border-light bg-white">
        <div className="flex items-center justify-between border-b border-border-light px-3 py-2">
          <div className="text-xs font-semibold text-text-main">Collection JSON</div>
          <button
            type="button"
            onClick={() => navigator.clipboard.writeText(safeJson(collectionInfo?.info || {}))}
            className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs text-text-main hover:bg-surface-light"
          >
            <Copy size={12} />
            Copy JSON
          </button>
        </div>
        {error && <div className="p-3"><ErrorState message={error} onRetry={refresh} /></div>}
        <pre className="h-full max-h-[calc(100%-33px)] overflow-auto p-3 text-[11px] leading-[1.4] text-text-main">
          {safeJson(collectionInfo?.info || {})}
        </pre>
      </div>
    </div>
  );
};

export default InfoTab;

