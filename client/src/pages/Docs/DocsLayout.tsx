import React, { useState, useEffect, useCallback } from 'react';
import { useDocsRoutes } from './hooks/useDocsRoutes';
import DocsSidebar from './components/Sidebar/DocsSidebar';
import DocsContent from './components/Content/DocsContent';
import TableOfContents from './components/TOC/TableOfContents';
import DocsSearch from './components/Search/DocsSearch';
import { PanelLeft } from 'lucide-react';
import type { TocHeading } from './types';

interface DocsLayoutProps {
  slug: string;
}

export default function DocsLayout({ slug }: DocsLayoutProps) {
  const { routes, loading, error } = useDocsRoutes();
  const [headings, setHeadings] = useState<TocHeading[]>([]);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // Handle keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Handle / key to open search
      if (e.key === '/' && !isSearchOpen) {
        const target = e.target as HTMLElement;
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          e.preventDefault();
          setIsSearchOpen(true);
        }
      }
      // Handle Escape key to close mobile sidebar
      if (e.key === 'Escape' && isMobileSidebarOpen) {
        setIsMobileSidebarOpen(false);
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen, isMobileSidebarOpen]);

  // Prevent body scroll when mobile sidebar is open
  useEffect(() => {
    if (isMobileSidebarOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobileSidebarOpen]);

  const handleCloseMobileSidebar = useCallback(() => {
    setIsMobileSidebarOpen(false);
  }, []);

  const handleOpenMobileSidebar = useCallback(() => {
    setIsMobileSidebarOpen(true);
  }, []);

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
    <div className="w-full max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4 flex gap-6 lg:gap-8 min-h-[calc(100vh-48px)]">
      {/* Mobile sidebar toggle button */}
      <button
        onClick={handleOpenMobileSidebar}
        className="fixed bottom-4 left-4 z-40 lg:hidden flex items-center justify-center
                   w-11 h-11 bg-surface border border-border rounded shadow-lg
                   hover:bg-surface-alt transition-colors"
        aria-label="Open navigation menu"
      >
        <PanelLeft className="w-5 h-5 text-text-secondary" />
      </button>

      {/* Mobile sidebar overlay */}
      {isMobileSidebarOpen && (
        <div
          className="fixed inset-0 z-50 lg:hidden"
          aria-modal="true"
          role="dialog"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={handleCloseMobileSidebar}
            aria-hidden="true"
          />
          {/* Drawer */}
          <div className="absolute left-0 top-0 h-full w-72 max-w-[85vw] bg-surface shadow-xl
                          animate-in slide-in-from-left duration-200">
            <DocsSidebar
              routes={routes}
              currentSlug={slug}
              loading={loading}
              onOpenSearch={handleOpenSearch}
              onClose={handleCloseMobileSidebar}
              isMobile
            />
          </div>
        </div>
      )}

      {/* Left Sidebar - Desktop */}
      <div className="hidden lg:block w-64 xl:w-72 2xl:w-80 shrink-0">
        <DocsSidebar
          routes={routes}
          currentSlug={slug}
          loading={loading}
          onOpenSearch={handleOpenSearch}
        />
      </div>

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
