import React, { useState, useEffect } from 'react';
import { useAuth } from '../../../../../auth/useAuth';
import { fetchControlVersions, fetchControlDiff } from '../../../api/explorerApi';
import type { ControlVersionSummary, ControlDiffData, ControlVersionSnapshot } from '../../types';
import { DiffField } from '../components/DiffField';

interface Props {
    controlId: string;
}

const MATERIAL_FIELDS: { key: keyof ControlVersionSnapshot; label: string; type: 'text' | 'bool' | 'list' | 'long' }[] = [
    { key: 'parent_control_id', label: 'Parent Control', type: 'text' },
    { key: 'control_status', label: 'Status', type: 'text' },
    { key: 'key_control', label: 'Key Control', type: 'bool' },
    { key: 'control_title', label: 'Title', type: 'long' },
    { key: 'control_description', label: 'Description', type: 'long' },
    { key: 'evidence_description', label: 'Evidence', type: 'long' },
    { key: 'local_functional_information', label: 'Functional Info', type: 'long' },
    { key: 'execution_frequency', label: 'Frequency', type: 'text' },
    { key: 'preventative_detective', label: 'Prev / Detective', type: 'text' },
    { key: 'manual_automated', label: 'Manual / Automated', type: 'text' },
    { key: 'control_administrator', label: 'Administrators', type: 'list' },
    { key: 'control_owner', label: 'Owner', type: 'text' },
    { key: 'control_owner_gpn', label: 'Owner GPN', type: 'text' },
    { key: 'last_modified_on', label: 'Last Modified', type: 'text' },
];

const formatDate = (d: string) => {
    try {
        return new Date(d).toLocaleString('en-GB', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch {
        return d;
    }
};

export const HistoryTab: React.FC<Props> = ({ controlId }) => {
    const { getApiAccessToken } = useAuth();
    const [versions, setVersions] = useState<ControlVersionSummary[]>([]);
    const [loadingVersions, setLoadingVersions] = useState(true);
    const [fromTx, setFromTx] = useState<string>('');
    const [toTx, setToTx] = useState<string>('');
    const [diff, setDiff] = useState<ControlDiffData | null>(null);
    const [loadingDiff, setLoadingDiff] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Load version list
    useEffect(() => {
        let cancelled = false;
        (async () => {
            setLoadingVersions(true);
            try {
                const token = await getApiAccessToken();
                if (!token || cancelled) return;
                const res = await fetchControlVersions(token, controlId);
                if (!cancelled) {
                    setVersions(res.versions);
                    // Default: compare second-to-last vs last (current)
                    if (res.versions.length >= 2) {
                        setFromTx(res.versions[res.versions.length - 2].tx_from);
                        setToTx(res.versions[res.versions.length - 1].tx_from);
                    }
                }
            } catch (e: unknown) {
                if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load versions');
            } finally {
                if (!cancelled) setLoadingVersions(false);
            }
        })();
        return () => { cancelled = true; };
    }, [controlId, getApiAccessToken]);

    // Load diff when both selections change
    useEffect(() => {
        if (!fromTx || !toTx || fromTx === toTx) {
            setDiff(null);
            return;
        }

        let cancelled = false;
        const controller = new AbortController();

        (async () => {
            setLoadingDiff(true);
            try {
                const token = await getApiAccessToken();
                if (!token || cancelled) return;
                const result = await fetchControlDiff(token, controlId, fromTx, toTx, controller.signal);
                if (!cancelled) setDiff(result);
            } catch (e: unknown) {
                if (!cancelled && !(e instanceof DOMException && e.name === 'AbortError')) {
                    setError(e instanceof Error ? e.message : 'Failed to load diff');
                }
            } finally {
                if (!cancelled) setLoadingDiff(false);
            }
        })();

        return () => { cancelled = true; controller.abort(); };
    }, [controlId, fromTx, toTx, getApiAccessToken]);

    if (loadingVersions) {
        return (
            <div className="flex items-center justify-center h-32 text-text-sub">
                <span className="material-symbols-outlined animate-spin text-[20px] mr-2">progress_activity</span>
                <span className="text-xs">Loading version history...</span>
            </div>
        );
    }

    if (versions.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-32 text-text-sub">
                <span className="material-symbols-outlined text-[24px] mb-1">history</span>
                <span className="text-xs">No version history available</span>
            </div>
        );
    }

    if (versions.length === 1) {
        return (
            <div className="flex flex-col items-center justify-center h-32 text-text-sub">
                <span className="material-symbols-outlined text-[24px] mb-1">history</span>
                <span className="text-xs">Only one version exists — no changes to compare</span>
            </div>
        );
    }

    return (
        <div>
            {/* Version pickers */}
            <div className="flex items-center gap-3 mb-4">
                <div className="flex-1">
                    <label className="block text-[10px] text-text-sub mb-0.5 font-medium uppercase tracking-wide">From (older)</label>
                    <select
                        value={fromTx}
                        onChange={e => setFromTx(e.target.value)}
                        className="w-full text-[11px] border border-border-light rounded px-2 py-1 bg-white text-text-main"
                    >
                        <option value="">Select version...</option>
                        {versions.map((v, i) => (
                            <option key={v.tx_from} value={v.tx_from}>
                                v{i + 1} — {formatDate(v.tx_from)}{!v.tx_to ? ' (current)' : ''}
                            </option>
                        ))}
                    </select>
                </div>
                <span className="material-symbols-outlined text-[16px] text-text-sub mt-3">arrow_forward</span>
                <div className="flex-1">
                    <label className="block text-[10px] text-text-sub mb-0.5 font-medium uppercase tracking-wide">To (newer)</label>
                    <select
                        value={toTx}
                        onChange={e => setToTx(e.target.value)}
                        className="w-full text-[11px] border border-border-light rounded px-2 py-1 bg-white text-text-main"
                    >
                        <option value="">Select version...</option>
                        {versions.map((v, i) => (
                            <option key={v.tx_from} value={v.tx_from}>
                                v{i + 1} — {formatDate(v.tx_from)}{!v.tx_to ? ' (current)' : ''}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            {error && (
                <div className="text-xs text-red-500 mb-3">{error}</div>
            )}

            {/* Diff view */}
            {loadingDiff ? (
                <div className="flex items-center justify-center h-24 text-text-sub">
                    <span className="material-symbols-outlined animate-spin text-[16px] mr-2">progress_activity</span>
                    <span className="text-xs">Loading comparison...</span>
                </div>
            ) : diff ? (
                <div className="space-y-1">
                    {MATERIAL_FIELDS.map(field => (
                        <DiffField
                            key={field.key}
                            label={field.label}
                            oldValue={diff.from_version[field.key]}
                            newValue={diff.to_version[field.key]}
                            fieldType={field.type}
                        />
                    ))}
                </div>
            ) : fromTx && toTx && fromTx !== toTx ? (
                <div className="text-xs text-text-sub text-center py-6">Select two different versions to compare</div>
            ) : null}
        </div>
    );
};
