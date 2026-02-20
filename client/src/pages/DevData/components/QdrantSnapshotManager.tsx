/**
 * Qdrant Snapshot Manager Component
 * Provides UI for creating, restoring, and managing Qdrant snapshots
 */

import React, { useState } from 'react';
import { AlertTriangle, Database, Loader2, PlusCircle, RotateCcw, Trash2 } from 'lucide-react';
import { useQdrantSnapshots } from '../hooks/useQdrantSnapshots';

const BUTTON_BASE =
    'inline-flex h-8 items-center gap-1.5 rounded-[2px] px-3 text-[12px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50';

interface CreateModalProps {
    isOpen: boolean;
    collections: string[];
    onClose: () => void;
    onCreate: (name: string, description: string, collection: string) => Promise<string | null>;
}

const CreateModal: React.FC<CreateModalProps> = ({ isOpen, collections, onClose, onCreate }) => {
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [collection, setCollection] = useState(collections[0] || '');
    const [isCreating, setIsCreating] = useState(false);

    // Sync default collection when collections load
    React.useEffect(() => {
        if (collections.length > 0 && !collection) {
            setCollection(collections[0]);
        }
    }, [collections, collection]);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!name.trim() || !collection) return;

        setIsCreating(true);
        const snapshotId = await onCreate(name, description, collection);
        setIsCreating(false);

        if (snapshotId) {
            setName('');
            setDescription('');
            onClose();
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-3">
            <div className="w-full max-w-[520px] rounded-[4px] border border-[#cccabc] bg-[#ffffff] p-5 shadow-[0_8px_24px_rgba(0,0,0,0.08)]">
                <h2 className="mb-4 text-[18px] font-semibold leading-[26px] text-[#1c1c1c]">
                    Create Qdrant Snapshot
                </h2>
                <form onSubmit={handleSubmit}>
                    <div className="mb-4">
                        <label className="mb-1 block text-[12px] font-medium leading-[18px] text-[#5a5d5c]">
                            Collection *
                        </label>
                        <select
                            value={collection}
                            onChange={(e) => setCollection(e.target.value)}
                            className="h-9 w-full rounded-[2px] border border-[#cccabc] px-3 text-[13px] text-[#1c1c1c] outline-none transition-colors focus:border-[#e60000]"
                            disabled={isCreating}
                            required
                        >
                            {collections.length === 0 && (
                                <option value="">Loading collections...</option>
                            )}
                            {collections.map((c) => (
                                <option key={c} value={c}>
                                    {c}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="mb-4">
                        <label className="mb-1 block text-[12px] font-medium leading-[18px] text-[#5a5d5c]">
                            Snapshot Name *
                        </label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="h-9 w-full rounded-[2px] border border-[#cccabc] px-3 text-[13px] text-[#1c1c1c] outline-none transition-colors placeholder:text-[#8e8d83] focus:border-[#e60000]"
                            placeholder="e.g., Pre-deployment backup"
                            required
                            disabled={isCreating}
                        />
                    </div>
                    <div className="mb-4">
                        <label className="mb-1 block text-[12px] font-medium leading-[18px] text-[#5a5d5c]">
                            Description (optional)
                        </label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            className="w-full rounded-[2px] border border-[#cccabc] px-3 py-2 text-[13px] text-[#1c1c1c] outline-none transition-colors placeholder:text-[#8e8d83] focus:border-[#e60000]"
                            rows={3}
                            placeholder="Additional notes about this snapshot..."
                            disabled={isCreating}
                        />
                    </div>
                    <div className="flex justify-end gap-2">
                        <button
                            type="button"
                            onClick={onClose}
                            className={`${BUTTON_BASE} border border-[#cccabc] bg-[#f9f9f7] text-[#5a5d5c] hover:bg-[#f4f3ee]`}
                            disabled={isCreating}
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className={`${BUTTON_BASE} bg-[#e60000] text-white hover:bg-[#da0000]`}
                            disabled={isCreating || !name.trim() || !collection}
                        >
                            {isCreating ? (
                                <>
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    Creating...
                                </>
                            ) : (
                                <>
                                    <PlusCircle className="h-3.5 w-3.5" />
                                    Create Snapshot
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

interface RestoreModalProps {
    isOpen: boolean;
    snapshot: any;
    onClose: () => void;
    onConfirm: () => Promise<boolean>;
}

const RestoreModal: React.FC<RestoreModalProps> = ({ isOpen, snapshot, onClose, onConfirm }) => {
    const [isRestoring, setIsRestoring] = useState(false);

    if (!isOpen || !snapshot) return null;

    const handleConfirm = async () => {
        setIsRestoring(true);
        const success = await onConfirm();
        setIsRestoring(false);
        if (success) onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-3">
            <div className="w-full max-w-[560px] rounded-[4px] border border-[#cccabc] bg-[#ffffff] p-5 shadow-[0_8px_24px_rgba(0,0,0,0.08)]">
                <h2 className="mb-4 flex items-center gap-2 text-[18px] font-semibold leading-[26px] text-[#c81219]">
                    <AlertTriangle className="h-4 w-4" />
                    Restore Qdrant Collection
                </h2>
                <div className="mb-4">
                    <p className="mb-2 text-[13px] leading-[20px] text-[#5a5d5c]">
                        You are about to restore a Qdrant collection from snapshot:
                    </p>
                    <div className="rounded-[3px] border border-[#e0dfd7] bg-[#f9f9f7] p-3">
                        <p className="text-[13px] font-medium leading-[20px] text-[#1c1c1c]">
                            {snapshot.name}
                        </p>
                        <p className="text-[12px] leading-[18px] text-[#5a5d5c]">ID: {snapshot.id}</p>
                        <p className="text-[12px] leading-[18px] text-[#5a5d5c]">
                            Collection: {snapshot.collection_name}
                        </p>
                        <p className="text-[12px] leading-[18px] text-[#5a5d5c]">
                            Created: {new Date(snapshot.created_at).toLocaleString()}
                        </p>
                    </div>
                </div>
                <div className="mb-4 rounded-[3px] border border-[#f2e4ba] bg-[#fbf4df] p-3">
                    <p className="text-[12px] leading-[18px] text-[#8c6400]">
                        <strong>Warning:</strong> This will replace the Qdrant collection data. The
                        current collection content will be overwritten with the snapshot data.
                    </p>
                </div>
                <div className="flex justify-end gap-2">
                    <button
                        onClick={onClose}
                        className={`${BUTTON_BASE} border border-[#cccabc] bg-[#f9f9f7] text-[#5a5d5c] hover:bg-[#f4f3ee]`}
                        disabled={isRestoring}
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleConfirm}
                        className={`${BUTTON_BASE} bg-[#c81219] text-white hover:bg-[#ab1117]`}
                        disabled={isRestoring}
                    >
                        {isRestoring ? (
                            <>
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                Restoring...
                            </>
                        ) : (
                            <>
                                <RotateCcw className="h-3.5 w-3.5" />
                                Restore Collection
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

const QdrantSnapshotManager: React.FC = () => {
    const {
        snapshots,
        total,
        page,
        hasMore,
        collections,
        loading,
        creating,
        restoring,
        deleting,
        currentJob,
        jobProgress,
        jobStep,
        error,
        createSnapshot,
        restoreSnapshot,
        deleteSnapshot,
        changePage,
        formatFileSize,
        formatDate,
    } = useQdrantSnapshots();

    const [showCreateModal, setShowCreateModal] = useState(false);
    const [restoreTarget, setRestoreTarget] = useState<any>(null);

    const handleCreate = async (name: string, description: string, collection: string) => {
        return await createSnapshot({ name, description, collection_name: collection });
    };

    const handleRestore = async () => {
        if (!restoreTarget) return false;
        return await restoreSnapshot(restoreTarget.id, {});
    };

    const handleDelete = async (snapshot: any) => {
        if (!window.confirm(`Are you sure you want to delete Qdrant snapshot "${snapshot.name}"?`)) {
            return;
        }
        await deleteSnapshot(snapshot.id);
    };

    return (
        <div className="p-4 sm:p-5">
            {/* Header */}
            <div className="mb-5">
                <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-[18px] font-semibold leading-[26px] text-[#1c1c1c]">
                        Qdrant Snapshots
                    </h2>
                    <button
                        onClick={() => setShowCreateModal(true)}
                        className={`${BUTTON_BASE} bg-[#e60000] text-white hover:bg-[#da0000]`}
                        disabled={creating || restoring}
                    >
                        <PlusCircle className="h-3.5 w-3.5" />
                        Create Snapshot
                    </button>
                </div>

                {/* Progress Bar */}
                {(creating || restoring) && (
                    <div className="mb-3 rounded-[3px] border border-[#e0dfd7] bg-[#f9f9f7] p-3">
                        <div className="mb-2 flex items-center justify-between">
                            <span className="text-[12px] font-medium leading-[18px] text-[#1c1c1c]">
                                {creating
                                    ? 'Qdrant Snapshot Creation Running'
                                    : 'Qdrant Snapshot Restore Running'}
                            </span>
                            <span className="font-mono text-[11px] leading-[16px] text-[#5a5d5c]">
                                {jobProgress}%
                            </span>
                        </div>
                        <div className="mb-2 h-1.5 w-full rounded-full bg-[#e0dfd7]">
                            <div
                                className="h-1.5 rounded-full bg-[#e60000] transition-all duration-300"
                                style={{ width: `${jobProgress}%` }}
                            />
                        </div>
                        <p className="text-[11px] leading-[16px] text-[#5a5d5c]">{jobStep}</p>
                        {currentJob?.job_id && (
                            <p className="mt-1 text-[11px] leading-[16px] text-[#5a5d5c]">
                                Job: <span className="font-mono">{currentJob.job_id}</span>
                            </p>
                        )}
                        <p className="mt-1 text-[11px] leading-[16px] text-[#5a5d5c]">
                            This runs in the background. You can continue using other Dev Data tabs.
                        </p>
                    </div>
                )}

                {/* Error */}
                {error && (
                    <div className="mb-3 rounded-[3px] border border-[#f2c7cb] bg-[#fdeeee] p-3">
                        <p className="text-[12px] leading-[18px] text-[#c81219]">{error}</p>
                    </div>
                )}
            </div>

            {/* Table */}
            <div className="overflow-hidden rounded-[3px] border border-[#cccabc] bg-[#ffffff]">
                <table className="w-full">
                    <thead className="border-b border-[#e0dfd7] bg-[#f9f9f7]">
                        <tr>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.04em] text-[#8e8d83]">
                                Snapshot
                            </th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.04em] text-[#8e8d83]">
                                Collection
                            </th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.04em] text-[#8e8d83]">
                                Points
                            </th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.04em] text-[#8e8d83]">
                                Size
                            </th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.04em] text-[#8e8d83]">
                                Created
                            </th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.04em] text-[#8e8d83]">
                                Status
                            </th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.04em] text-[#8e8d83]">
                                Restored
                            </th>
                            <th className="px-4 py-2.5 text-right text-[10px] font-medium uppercase tracking-[0.04em] text-[#8e8d83]">
                                Actions
                            </th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-[#e0dfd7]">
                        {loading && !snapshots.length ? (
                            <tr>
                                <td colSpan={8} className="px-4 py-8 text-center text-[#5a5d5c]">
                                    <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                                    <p className="mt-2 text-[12px] leading-[18px]">
                                        Loading Qdrant snapshots...
                                    </p>
                                </td>
                            </tr>
                        ) : snapshots.length === 0 ? (
                            <tr>
                                <td
                                    colSpan={8}
                                    className="px-4 py-10 text-center text-[#5a5d5c]"
                                >
                                    <Database className="mx-auto h-10 w-10 text-[#8e8d83]" />
                                    <p className="mt-2 text-[13px] leading-[20px] text-[#1c1c1c]">
                                        No Qdrant snapshots found
                                    </p>
                                    <p className="mt-1 text-[12px] leading-[18px]">
                                        Create your first Qdrant snapshot to get started
                                    </p>
                                </td>
                            </tr>
                        ) : (
                            snapshots.map((snapshot) => (
                                <tr key={snapshot.id} className="hover:bg-[#f9f9f7]">
                                    <td className="px-4 py-3">
                                        <div>
                                            <p className="text-[13px] font-medium leading-[20px] text-[#1c1c1c]">
                                                {snapshot.name}
                                            </p>
                                            <p className="font-mono text-[11px] leading-[16px] text-[#8e8d83]">
                                                {snapshot.id}
                                            </p>
                                        </div>
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className="font-mono text-[12px] leading-[18px] text-[#1c1c1c]">
                                            {snapshot.collection_name}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className="font-mono text-[12px] leading-[18px] text-[#1c1c1c]">
                                            {snapshot.points_count.toLocaleString()}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className="font-mono text-[12px] leading-[18px] text-[#1c1c1c]">
                                            {formatFileSize(snapshot.file_size)}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3">
                                        <div className="text-[12px] leading-[18px] text-[#1c1c1c]">
                                            {formatDate(snapshot.created_at)}
                                        </div>
                                        <div className="text-[11px] leading-[16px] text-[#5a5d5c]">
                                            by {snapshot.created_by}
                                        </div>
                                    </td>
                                    <td className="px-4 py-3">
                                        <span
                                            className={`inline-flex rounded-[2px] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.03em] ${
                                                snapshot.status === 'completed'
                                                    ? 'bg-[#edf5df] text-[#498100]'
                                                    : snapshot.status === 'failed'
                                                    ? 'bg-[#fdeeee] text-[#c81219]'
                                                    : 'bg-[#fbf4df] text-[#8c6400]'
                                            }`}
                                        >
                                            {snapshot.status}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className="text-[12px] leading-[18px] text-[#1c1c1c]">
                                            {snapshot.restored_count} times
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <div className="flex justify-end gap-1">
                                            <button
                                                onClick={() => setRestoreTarget(snapshot)}
                                                className="inline-flex h-7 w-7 items-center justify-center rounded-[2px] text-[#5a5d5c] transition-colors hover:bg-[#f4f3ee] hover:text-[#1c1c1c] disabled:opacity-40"
                                                disabled={
                                                    snapshot.status !== 'completed' ||
                                                    creating ||
                                                    restoring ||
                                                    deleting
                                                }
                                                title="Restore from this snapshot"
                                            >
                                                <RotateCcw className="h-3.5 w-3.5" />
                                            </button>
                                            <button
                                                onClick={() => handleDelete(snapshot)}
                                                className="inline-flex h-7 w-7 items-center justify-center rounded-[2px] text-[#c81219] transition-colors hover:bg-[#fdeeee] disabled:opacity-40"
                                                disabled={creating || restoring || deleting}
                                                title="Delete this snapshot"
                                            >
                                                <Trash2 className="h-3.5 w-3.5" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>

                {/* Pagination */}
                {total > snapshots.length && (
                    <div className="flex items-center justify-between border-t border-[#e0dfd7] bg-[#f9f9f7] px-4 py-2.5">
                        <p className="text-[12px] leading-[18px] text-[#5a5d5c]">
                            Showing {snapshots.length} of {total} snapshots
                        </p>
                        <div className="flex gap-2">
                            <button
                                onClick={() => changePage(page - 1)}
                                disabled={page === 1 || loading}
                                className={`${BUTTON_BASE} border border-[#cccabc] bg-[#ffffff] text-[#5a5d5c] hover:bg-[#f4f3ee]`}
                            >
                                Previous
                            </button>
                            <span className="inline-flex h-8 items-center px-2 font-mono text-[11px] text-[#5a5d5c]">
                                Page {page}
                            </span>
                            <button
                                onClick={() => changePage(page + 1)}
                                disabled={!hasMore || loading}
                                className={`${BUTTON_BASE} border border-[#cccabc] bg-[#ffffff] text-[#5a5d5c] hover:bg-[#f4f3ee]`}
                            >
                                Next
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* Modals */}
            <CreateModal
                isOpen={showCreateModal}
                collections={collections}
                onClose={() => setShowCreateModal(false)}
                onCreate={handleCreate}
            />
            <RestoreModal
                isOpen={!!restoreTarget}
                snapshot={restoreTarget}
                onClose={() => setRestoreTarget(null)}
                onConfirm={handleRestore}
            />
        </div>
    );
};

export default QdrantSnapshotManager;
