import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useDocsSearch } from '../../hooks/useDocsSearch';
import SearchResults from './SearchResults';

interface DocsSearchProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function DocsSearch({ isOpen, onClose }: DocsSearchProps) {
  const [query, setQuery] = useState('');
  const { search, isReady } = useDocsSearch();
  const inputRef = useRef<HTMLInputElement>(null);

  const results = query.trim() ? search(query) : [];

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Clear query when modal closes
  useEffect(() => {
    if (!isOpen) {
      setQuery('');
    }
  }, [isOpen]);

  // Handle keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Open with / key
      if (e.key === '/' && !isOpen) {
        const target = e.target as HTMLElement;
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          e.preventDefault();
          // This should be handled by parent
        }
      }

      // Close with Escape
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleResultClick = useCallback(() => {
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-2xl mx-4 bg-surface border border-border rounded-xl shadow-2xl overflow-hidden">
        {/* Search input */}
        <div className="flex items-center gap-3 p-4 border-b border-border">
          <span className="material-symbols-outlined text-text-tertiary">search</span>
          <input
            ref={inputRef}
            type="text"
            placeholder={isReady ? 'Search documentation...' : 'Loading search index...'}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={!isReady}
            className="flex-1 bg-transparent text-text-primary placeholder:text-text-tertiary
                       focus:outline-none text-lg"
          />
          <button
            onClick={onClose}
            className="text-text-tertiary hover:text-text-secondary transition-colors"
          >
            <kbd className="px-2 py-1 text-xs bg-surface-alt rounded border border-border">
              ESC
            </kbd>
          </button>
        </div>

        {/* Results */}
        {query.trim() && (
          <SearchResults
            results={results}
            onResultClick={handleResultClick}
          />
        )}

        {/* No query state */}
        {!query.trim() && (
          <div className="p-8 text-center">
            <span className="material-symbols-outlined text-4xl text-text-tertiary mb-2">
              search
            </span>
            <p className="text-text-secondary">Start typing to search the docs</p>
            <div className="flex items-center justify-center gap-4 mt-4 text-xs text-text-tertiary">
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-surface-alt rounded border border-border">Enter</kbd>
                to select
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 bg-surface-alt rounded border border-border">ESC</kbd>
                to close
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
