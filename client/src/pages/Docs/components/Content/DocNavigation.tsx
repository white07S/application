import React from 'react';
import { Link } from 'react-router-dom';
import type { DocsNavigation } from '../../types';

interface DocNavigationProps {
  navigation: DocsNavigation;
}

export default function DocNavigation({ navigation }: DocNavigationProps) {
  const { prev, next } = navigation;

  if (!prev && !next) return null;

  return (
    <nav className="mt-12 pt-6 border-t border-border flex items-stretch gap-4">
      {prev ? (
        <Link
          to={`/docs/${prev.slug}`}
          className="flex-1 p-4 rounded-lg border border-border hover:border-primary/50
                     hover:bg-primary/5 transition-colors group"
        >
          <div className="flex items-center gap-2 text-xs text-text-tertiary mb-1">
            <span className="material-symbols-outlined text-sm group-hover:-translate-x-1 transition-transform">
              arrow_back
            </span>
            Previous
          </div>
          <div className="font-medium text-text-primary">{prev.title}</div>
          <div className="text-xs text-text-tertiary mt-1">{prev.category}</div>
        </Link>
      ) : (
        <div className="flex-1" />
      )}

      {next ? (
        <Link
          to={`/docs/${next.slug}`}
          className="flex-1 p-4 rounded-lg border border-border hover:border-primary/50
                     hover:bg-primary/5 transition-colors text-right group"
        >
          <div className="flex items-center justify-end gap-2 text-xs text-text-tertiary mb-1">
            Next
            <span className="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">
              arrow_forward
            </span>
          </div>
          <div className="font-medium text-text-primary">{next.title}</div>
          <div className="text-xs text-text-tertiary mt-1">{next.category}</div>
        </Link>
      ) : (
        <div className="flex-1" />
      )}
    </nav>
  );
}
