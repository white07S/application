import React from 'react';
import { X, Search } from 'lucide-react';
import type { DocsRoutes } from '../../types';
import CategoryItem from './CategoryItem';

interface DocsSidebarProps {
  routes: DocsRoutes | null;
  currentSlug: string;
  loading: boolean;
  onOpenSearch: () => void;
  onClose?: () => void;
  isMobile?: boolean;
}

export default function DocsSidebar({
  routes,
  currentSlug,
  loading,
  onOpenSearch,
  onClose,
  isMobile = false
}: DocsSidebarProps) {
  // Base styles for sidebar - adapts for mobile drawer or desktop sticky
  const sidebarBaseClass = isMobile
    ? 'w-full h-full overflow-y-auto bg-surface'
    : 'w-full border-r border-border overflow-y-auto h-[calc(100vh-48px)] sticky top-12';

  if (loading) {
    return (
      <aside className={sidebarBaseClass}>
        <div className="p-4">
          {/* Mobile close button */}
          {isMobile && onClose && (
            <div className="flex items-center justify-between mb-4 pb-4 border-b border-border">
              <span className="text-sm font-medium text-text-primary">Documentation</span>
              <button
                onClick={onClose}
                className="flex items-center justify-center w-10 h-10 rounded hover:bg-surface-alt transition-colors"
                aria-label="Close navigation"
              >
                <X className="w-5 h-5 text-text-secondary" />
              </button>
            </div>
          )}
          <div className="animate-pulse space-y-3">
            <div className="h-10 bg-surface-alt rounded" />
            <div className="h-10 bg-surface-alt rounded w-3/4" />
            <div className="h-10 bg-surface-alt rounded w-2/3" />
            <div className="h-10 bg-surface-alt rounded w-3/4" />
          </div>
        </div>
      </aside>
    );
  }

  const categories = routes?.categories || [];

  return (
    <aside className={sidebarBaseClass}>
      <div className="p-4">
        {/* Mobile close button */}
        {isMobile && onClose && (
          <div className="flex items-center justify-between mb-4 pb-4 border-b border-border">
            <span className="text-sm font-medium text-text-primary">Documentation</span>
            <button
              onClick={onClose}
              className="flex items-center justify-center w-10 h-10 rounded hover:bg-surface-alt transition-colors"
              aria-label="Close navigation"
            >
              <X className="w-5 h-5 text-text-secondary" />
            </button>
          </div>
        )}

        {/* Search button - touch-friendly height (44px) */}
        <button
          onClick={() => {
            onOpenSearch();
            if (isMobile && onClose) {
              onClose();
            }
          }}
          className="w-full flex items-center gap-2 px-3 py-2 min-h-[36px] text-xs text-text-secondary
                     bg-surface-alt rounded border border-border hover:border-text-tertiary
                     transition-colors mb-4"
        >
          <Search className="w-4 h-4 shrink-0" />
          <span className="flex-1 text-left">Search docs...</span>
          {!isMobile && (
            <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-xs bg-surface rounded border border-border">
              /
            </kbd>
          )}
        </button>

        {/* Navigation */}
        <nav className={isMobile ? 'space-y-1' : ''}>
          {categories.map(category => (
            <CategoryItem
              key={category.id}
              category={category}
              currentSlug={currentSlug}
            />
          ))}
        </nav>
      </div>
    </aside>
  );
}
