import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Download, RefreshCw } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { qdrantBrowserApi } from '../../api/qdrantBrowserApi';
import { CollectionClusterResponse, SnapshotListItem } from '../../types';
import ErrorState from '../ErrorState';
import EmptyState from '../EmptyState';
import { downloadBlob, formatBytes } from '../../utils/formatters';

interface SnapshotsTabProps {
  collectionName: string;
}

const SnapshotsTab: React.FC<SnapshotsTabProps> = ({ collectionName }) => {
  const { getApiAccessToken } = useAuth();
  const [snapshots, setSnapshots] = useState<SnapshotListItem[]>([]);
  const [cluster, setCluster] = useState<CollectionClusterResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<Record<string, number>>({});

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }
      const [snapshotsResponse, clusterResponse] = await Promise.all([
        qdrantBrowserApi.getSnapshots(token, collectionName),
        qdrantBrowserApi.getCollectionCluster(token, collectionName),
      ]);
      setSnapshots(snapshotsResponse.snapshots || []);
      setCluster(clusterResponse);
    } catch (err: any) {
      setError(err?.message || 'Failed to load snapshots');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionName]);

  const remoteShards = useMemo(() => cluster?.remote_shards || [], [cluster?.remote_shards]);
  const localShards = useMemo(() => cluster?.local_shards || [], [cluster?.local_shards]);

  const downloadSnapshot = async (snapshot: SnapshotListItem) => {
    try {
      const token = await getApiAccessToken();
      if (!token) {
        return;
      }

      setDownloadProgress((current) => ({ ...current, [snapshot.name]: 0 }));
      const { blob, filename } = await qdrantBrowserApi.downloadSnapshot(
        token,
        collectionName,
        snapshot.name,
        (loaded, total) => {
          if (!total) {
            return;
          }
          setDownloadProgress((current) => ({
            ...current,
            [snapshot.name]: Math.min(100, Math.round((loaded / total) * 100)),
          }));
        }
      );
      downloadBlob(blob, filename);
      setDownloadProgress((current) => ({ ...current, [snapshot.name]: 100 }));
      setTimeout(() => {
        setDownloadProgress((current) => ({ ...current, [snapshot.name]: 0 }));
      }, 800);
    } catch (err: any) {
      setError(err?.message || 'Snapshot download failed');
      setDownloadProgress((current) => ({ ...current, [snapshot.name]: 0 }));
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden p-3">
      <div className="rounded border border-border-light bg-white">
        <div className="flex items-center justify-between border-b border-border-light px-3 py-2">
          <div className="text-xs font-semibold text-text-main">Snapshots</div>
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

        {remoteShards.length > 0 && (
          <div className="border-b border-border-light bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
            <div className="mb-1 flex items-center gap-1 font-medium">
              <AlertTriangle size={12} />
              Snapshot excludes remote shards in distributed mode
            </div>
            <div>Local shards: {localShards.map((shard) => shard.shard_id).join(', ') || 'none'}</div>
            <div>Remote shards: {remoteShards.map((shard) => `${shard.shard_id} (${shard.peer_id})`).join(', ')}</div>
          </div>
        )}

        <div className="min-h-0 max-h-[calc(100vh-320px)] overflow-auto p-2">
          {loading ? (
            <div className="p-3 text-xs text-text-sub">Loading snapshots...</div>
          ) : snapshots.length === 0 ? (
            <EmptyState title="No snapshots found" />
          ) : (
            <table className="w-full min-w-[640px] text-xs">
              <thead>
                <tr className="text-left text-text-sub">
                  <th className="px-2 py-1 font-medium">Snapshot</th>
                  <th className="px-2 py-1 font-medium">Created</th>
                  <th className="px-2 py-1 font-medium">Size</th>
                  <th className="px-2 py-1 font-medium">Download</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((snapshot) => (
                  <tr key={snapshot.name} className="border-t border-border-light">
                    <td className="px-2 py-1 font-mono text-text-main">{snapshot.name}</td>
                    <td className="px-2 py-1 text-text-sub">{snapshot.creation_time || 'unknown'}</td>
                    <td className="px-2 py-1 text-text-sub">{formatBytes(snapshot.size)}</td>
                    <td className="px-2 py-1">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => downloadSnapshot(snapshot)}
                          className="inline-flex items-center gap-1 rounded border border-border-light bg-white px-2 py-1 text-xs text-text-main hover:bg-surface-light"
                        >
                          <Download size={12} />
                          Download
                        </button>
                        {(downloadProgress[snapshot.name] || 0) > 0 && (
                          <div className="h-1.5 w-28 overflow-hidden rounded bg-border-light">
                            <div
                              className="h-full bg-primary transition-all"
                              style={{ width: `${downloadProgress[snapshot.name]}%` }}
                            />
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={refresh} />}
    </div>
  );
};

export default SnapshotsTab;

