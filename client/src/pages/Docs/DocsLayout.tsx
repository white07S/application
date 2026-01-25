import React, { useState, useEffect, useCallback } from 'react';
import { useDocsRoutes } from './hooks/useDocsRoutes';
import DocsSidebar from './components/Sidebar/DocsSidebar';
import DocsContent from './components/Content/DocsContent';
import TableOfContents from './components/TOC/TableOfContents';
import DocsSearch from './components/Search/DocsSearch';
import type { TocHeading } from './types';

interface DocsLayoutProps {
  slug: string;
}

export default function DocsLayout({ slug }: DocsLayoutProps) {
  const { routes, loading, error } = useDocsRoutes();
  const [headings, setHeadings] = useState<TocHeading[]>([]);
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  // Handle / key to open search
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === '/' && !isSearchOpen) {
        const target = e.target as HTMLElement;
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          e.preventDefault();
          setIsSearchOpen(true);
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen]);

  const handleHeadingsExtracted = useCallback((extracted: TocHeading[]) => {
    setHeadings(extracted);
  }, []);

  const handleOpenSearch = useCallback(() => {
    setIsSearchOpen(true);
  }, []);

  const handleCloseSearch = useCallback(() => {
    setIsSearchOpen(false);
  }, []);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <span className="material-symbols-outlined text-6xl text-red-400 mb-4">error</span>
          <h2 className="text-xl font-semibold mb-2">Failed to load documentation</h2>
          <p className="text-text-secondary">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-48px)]">
      {/* Left Sidebar */}
      <DocsSidebar
        routes={routes}
        currentSlug={slug}
        loading={loading}
        onOpenSearch={handleOpenSearch}
      />

      {/* Main Content */}
      <DocsContent
        slug={slug}
        routes={routes}
        onHeadingsExtracted={handleHeadingsExtracted}
      />

      {/* Right Sidebar - Table of Contents */}
      <TableOfContents headings={headings} />

      {/* Search Modal */}
      <DocsSearch
        isOpen={isSearchOpen}
        onClose={handleCloseSearch}
      />
    </div>
  );
}
