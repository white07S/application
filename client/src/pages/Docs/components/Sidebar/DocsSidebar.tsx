import React from 'react';
import type { DocsRoutes } from '../../types';
import CategoryItem from './CategoryItem';

interface DocsSidebarProps {
  routes: DocsRoutes | null;
  currentSlug: string;
  loading: boolean;
  onOpenSearch: () => void;
}

export default function DocsSidebar({ routes, currentSlug, loading, onOpenSearch }: DocsSidebarProps) {
  if (loading) {
    return (
      <aside className="w-64 shrink-0 border-r border-border overflow-y-auto h-[calc(100vh-48px)] sticky top-12">
        <div className="p-4">
          <div className="animate-pulse space-y-3">
            <div className="h-8 bg-surface-alt rounded" />
            <div className="h-6 bg-surface-alt rounded w-3/4" />
            <div className="h-6 bg-surface-alt rounded w-2/3" />
            <div className="h-6 bg-surface-alt rounded w-3/4" />
          </div>
        </div>
      </aside>
    );
  }

  const categories = routes?.categories || [];

  return (
    <aside className="w-64 shrink-0 border-r border-border overflow-y-auto h-[calc(100vh-48px)] sticky top-12">
      <div className="p-4">
        {/* Search button */}
        <button
          onClick={onOpenSearch}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-text-secondary
                     bg-surface-alt rounded-md border border-border hover:border-text-tertiary
                     transition-colors mb-4"
        >
          <span className="material-symbols-outlined text-lg">search</span>
          <span className="flex-1 text-left">Search docs...</span>
          <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-xs bg-surface rounded border border-border">
            /
          </kbd>
        </button>

        {/* Navigation */}
        <nav>
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
