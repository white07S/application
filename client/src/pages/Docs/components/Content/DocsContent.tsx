import React from 'react';
import { useDocContent } from '../../hooks/useDocContent';
import { useDocsNavigation } from '../../hooks/useDocsRoutes';
import MDXRenderer from './MDXRenderer';
import Breadcrumb from './Breadcrumb';
import DocNavigation from './DocNavigation';
import type { DocsRoutes, TocHeading } from '../../types';

interface DocsContentProps {
  slug: string;
  routes: DocsRoutes | null;
  onHeadingsExtracted: (headings: TocHeading[]) => void;
}

export default function DocsContent({ slug, routes, onHeadingsExtracted }: DocsContentProps) {
  const { content, loading, error } = useDocContent(slug);
  const navigation = useDocsNavigation(routes, slug);

  // Find current doc info for breadcrumb
  const currentDoc = routes?.categories
    .flatMap(c => c.items.map(item => ({ ...item, categoryLabel: c.label })))
    .find(item => item.slug === slug);

  if (loading) {
    return (
      <div className="flex-1 min-w-0 py-8">
        <div className="w-full max-w-4xl xl:max-w-5xl 2xl:max-w-6xl">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-surface-alt rounded w-48" />
            <div className="h-10 bg-surface-alt rounded w-3/4" />
            <div className="h-6 bg-surface-alt rounded w-1/2" />
            <div className="h-4 bg-surface-alt rounded" />
            <div className="h-4 bg-surface-alt rounded w-5/6" />
            <div className="h-4 bg-surface-alt rounded w-4/5" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 min-w-0 py-8">
        <div className="w-full max-w-4xl xl:max-w-5xl 2xl:max-w-6xl">
          <div className="text-center py-16">
            <span className="material-symbols-outlined text-6xl text-text-tertiary mb-4">
              error_outline
            </span>
            <h2 className="text-xl font-semibold mb-2">Document Not Found</h2>
            <p className="text-text-secondary">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="flex-1 min-w-0 py-8">
        <div className="w-full max-w-4xl xl:max-w-5xl 2xl:max-w-6xl">
          <div className="text-center py-16">
            <span className="material-symbols-outlined text-6xl text-text-tertiary mb-4">
              article
            </span>
            <h2 className="text-xl font-semibold mb-2">No Content</h2>
            <p className="text-text-secondary">Select a document from the sidebar.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 min-w-0 py-8">
      <div className="w-full max-w-4xl xl:max-w-5xl 2xl:max-w-6xl">
        {currentDoc && (
          <Breadcrumb
            category={currentDoc.categoryLabel}
            title={currentDoc.title}
          />
        )}

        <MDXRenderer
          content={content}
          onHeadingsExtracted={onHeadingsExtracted}
        />

        <DocNavigation navigation={navigation} />
      </div>
    </div>
  );
}
