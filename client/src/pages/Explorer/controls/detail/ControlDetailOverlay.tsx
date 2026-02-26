import React, { useState, useEffect, useCallback } from 'react';
import { X } from 'lucide-react';
import { useAuth } from '../../../../auth/useAuth';
import { fetchControlDetail } from '../../api/explorerApi';
import type { ControlDetailData } from '../types';
import { ControlDetailHeader } from './ControlDetailHeader';
import { DetailsTab } from './tabs/DetailsTab';
import { RelationshipsTab } from './tabs/RelationshipsTab';
import { HistoryTab } from './tabs/HistoryTab';
import { AITab } from './tabs/AITab';

type TabKey = 'details' | 'relationships' | 'history' | 'ai';

const TABS: { key: TabKey; label: string; icon: string }[] = [
    { key: 'details', label: 'Details', icon: 'description' },
    { key: 'relationships', label: 'Relationships', icon: 'hub' },
    { key: 'history', label: 'History', icon: 'history' },
    { key: 'ai', label: 'AI', icon: 'auto_awesome' },
];

interface Props {
    controlId: string;
    onClose: () => void;
}

export const ControlDetailOverlay: React.FC<Props> = ({ controlId, onClose }) => {
    const { getApiAccessToken } = useAuth();
    const [activeTab, setActiveTab] = useState<TabKey>('details');
    const [data, setData] = useState<ControlDetailData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        const controller = new AbortController();

        (async () => {
            setLoading(true);
            setError(null);
            try {
                const token = await getApiAccessToken();
                if (!token || cancelled) return;
                const result = await fetchControlDetail(token, controlId, controller.signal);
                if (!cancelled) setData(result);
            } catch (e: unknown) {
                if (!cancelled && !(e instanceof DOMException && e.name === 'AbortError')) {
                    setError(e instanceof Error ? e.message : 'Failed to load control detail');
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();

        return () => {
            cancelled = true;
            controller.abort();
        };
    }, [controlId, getApiAccessToken]);

    // Close on Escape
    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', handleKey);
        return () => document.removeEventListener('keydown', handleKey);
    }, [onClose]);

    const renderTabContent = useCallback(() => {
        if (loading) {
            return (
                <div className="flex items-center justify-center h-40 text-text-sub">
                    <span className="material-symbols-outlined animate-spin text-[20px] mr-2">progress_activity</span>
                    <span className="text-xs">Loading...</span>
                </div>
            );
        }
        if (error) {
            return (
                <div className="flex items-center justify-center h-40 text-red-500">
                    <span className="material-symbols-outlined text-[20px] mr-2">error</span>
                    <span className="text-xs">{error}</span>
                </div>
            );
        }
        if (!data) return null;

        switch (activeTab) {
            case 'details':
                return <DetailsTab data={data} />;
            case 'relationships':
                return <RelationshipsTab data={data} />;
            case 'history':
                return <HistoryTab controlId={controlId} />;
            case 'ai':
                return <AITab data={data} />;
            default:
                return null;
        }
    }, [activeTab, data, loading, error, controlId]);

    return (
        <>
            {/* Backdrop — below the 48px header */}
            <div
                className="fixed inset-0 top-12 bg-black/20 z-30"
                onClick={onClose}
            />

            {/* Panel — below header */}
            <div className="fixed top-12 right-0 h-[calc(100vh-48px)] w-[40%] min-w-[480px] z-40 bg-white border-l border-border-light shadow-xl flex flex-col animate-slide-in-right">
                {/* Close button */}
                <button
                    onClick={onClose}
                    className="absolute top-2 right-2 z-10 p-1 rounded hover:bg-surface-light text-text-sub hover:text-text-main transition-colors"
                >
                    <X size={16} />
                </button>

                {/* Header */}
                {data && <ControlDetailHeader data={data} />}
                {!data && !loading && (
                    <div className="px-4 py-3 border-b border-border-light">
                        <span className="text-xs text-text-sub">{controlId}</span>
                    </div>
                )}

                {/* Tab bar */}
                <div className="flex border-b border-border-light px-4 gap-1 shrink-0">
                    {TABS.map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key)}
                            className={`flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium border-b-2 transition-colors ${
                                activeTab === tab.key
                                    ? 'border-primary text-primary'
                                    : 'border-transparent text-text-sub hover:text-text-main'
                            }`}
                        >
                            <span className="material-symbols-outlined text-[14px]">{tab.icon}</span>
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Tab content (scrollable) */}
                <div className="flex-1 overflow-y-auto p-4">
                    {renderTabContent()}
                </div>
            </div>
        </>
    );
};
