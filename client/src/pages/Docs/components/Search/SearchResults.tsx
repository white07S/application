import React from 'react';
import { Link } from 'react-router-dom';

interface SearchResult {
  id: string;
  title: string;
  content: string;
  path: string;
  anchor: string;
  category: string;
  docTitle: string;
  level: number;
  highlight?: string;
}

interface SearchResultsProps {
  results: SearchResult[];
  onResultClick: () => void;
}

export default function SearchResults({ results, onResultClick }: SearchResultsProps) {
  if (results.length === 0) {
    return (
      <div className="p-8 text-center">
        <span className="material-symbols-outlined text-4xl text-text-tertiary mb-2">
          search_off
        </span>
        <p className="text-text-secondary">No results found</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-border max-h-96 overflow-y-auto">
      {results.map(result => (
        <Link
          key={result.id}
          to={result.anchor}
          onClick={onResultClick}
          className="block p-4 hover:bg-surface-alt transition-colors"
        >
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-text-tertiary mt-0.5">
              {result.level === 0 ? 'article' : 'tag'}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-text-tertiary">{result.category}</span>
                {result.level > 0 && (
                  <>
                    <span className="text-text-tertiary">/</span>
                    <span className="text-xs text-text-tertiary">{result.docTitle}</span>
                  </>
                )}
              </div>
              <h4 className="font-medium text-text-primary truncate">{result.title}</h4>
              {result.highlight && (
                <p className="text-sm text-text-tertiary mt-1 line-clamp-2">
                  {result.highlight}
                </p>
              )}
            </div>
            <span className="material-symbols-outlined text-text-tertiary">
              arrow_forward
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
}
