import React, { useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { CollectionListItem } from '../types';

interface CollectionSelectorProps {
  collections: CollectionListItem[];
  value: string | null;
  loading: boolean;
  onChange: (nextCollection: string) => void;
}

const CollectionSelector: React.FC<CollectionSelectorProps> = ({ collections, value, loading, onChange }) => {
  const [query, setQuery] = useState(value || '');

  useEffect(() => {
    setQuery(value || '');
  }, [value]);

  const options = useMemo(() => collections.map((item) => item.name), [collections]);
  const filtered = useMemo(() => {
    if (!query.trim()) {
      return options;
    }
    return options.filter((item) => item.toLowerCase().includes(query.toLowerCase()));
  }, [options, query]);

  const listId = 'qdrant-collection-selector-options';

  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="relative min-w-[240px] max-w-[460px] w-full">
        <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-text-sub" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onBlur={() => {
            const selected = options.find((name) => name === query.trim());
            if (selected && selected !== value) {
              onChange(selected);
            } else if (value && query !== value) {
              setQuery(value);
            }
          }}
          list={listId}
          disabled={loading || options.length === 0}
          placeholder={loading ? 'Loading collections...' : 'Search collection'}
          className="w-full rounded border border-border-light bg-white pl-7 pr-2 py-1.5 text-xs text-text-main focus:outline-none focus:ring-1 focus:ring-primary/35"
        />
        <datalist id={listId}>
          {filtered.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      </div>

      <button
        type="button"
        disabled={loading || !query.trim() || query === value}
        onClick={() => {
          const selected = options.find((name) => name === query.trim());
          if (selected) {
            onChange(selected);
          }
        }}
        className="rounded border border-border-light bg-white px-2 py-1 text-xs font-medium text-text-main hover:bg-surface-light disabled:cursor-not-allowed disabled:opacity-40"
      >
        Select
      </button>
    </div>
  );
};

export default CollectionSelector;

