import React from 'react';
import { QdrantTabKey } from '../types';

interface QdrantTabNavProps {
  activeTab: QdrantTabKey;
  onChange: (tab: QdrantTabKey) => void;
}

const TAB_ITEMS: { key: QdrantTabKey; label: string }[] = [
  { key: 'points', label: 'Points' },
  { key: 'info', label: 'Info' },
  { key: 'quality', label: 'Search Quality' },
  { key: 'data_quality', label: 'Data Quality' },
  { key: 'vector_health', label: 'Vector Health' },
  { key: 'snapshots', label: 'Snapshots' },
  { key: 'cluster', label: 'Cluster' },
  { key: 'optimizations', label: 'Optimizations' },
  { key: 'visualize', label: 'Visualize' },
  { key: 'graph', label: 'Graph' },
];

const QdrantTabNav: React.FC<QdrantTabNavProps> = ({ activeTab, onChange }) => {
  return (
    <div className="flex items-center gap-1 overflow-x-auto border-b border-border-light bg-surface-light/70 px-2 py-1">
      {TAB_ITEMS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          className={`shrink-0 rounded px-2 py-1 text-xs transition-colors ${
            activeTab === tab.key
              ? 'bg-white border border-border-light text-text-main font-medium shadow-sm'
              : 'text-text-sub hover:text-text-main hover:bg-white'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
};

export default QdrantTabNav;
