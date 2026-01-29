import { useState, useEffect, useCallback, useMemo } from 'react';
import type { SearchIndex, SearchDocument } from '../types';
import { appConfig } from '../../../config/appConfig';

interface SearchResult extends SearchDocument {
  highlight?: string;
}

export function useDocsSearch() {
  const [searchIndex, setSearchIndex] = useState<SearchIndex | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchIndex() {
      try {
        const response = await fetch(`${appConfig.api.baseUrl}/api/docs/search-index`);
        if (!response.ok) {
          throw new Error('Failed to fetch search index');
        }
        const data = await response.json();
        setSearchIndex(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }

    fetchIndex();
  }, []);

  const search = useCallback((query: string): SearchResult[] => {
    if (!searchIndex || !query.trim()) return [];

    const normalizedQuery = query.toLowerCase().trim();
    const terms = normalizedQuery.split(/\s+/);

    const results: SearchResult[] = [];

    for (const doc of searchIndex.documents) {
      const titleLower = doc.title.toLowerCase();
      const contentLower = doc.content.toLowerCase();

      // Check if all terms match either title or content
      const matches = terms.every(term =>
        titleLower.includes(term) || contentLower.includes(term)
      );

      if (matches) {
        // Create highlight snippet
        let highlight = doc.content;
        const firstTermIndex = contentLower.indexOf(terms[0]);

        if (firstTermIndex !== -1) {
          const start = Math.max(0, firstTermIndex - 40);
          const end = Math.min(doc.content.length, firstTermIndex + terms[0].length + 80);
          highlight = (start > 0 ? '...' : '') +
                     doc.content.slice(start, end) +
                     (end < doc.content.length ? '...' : '');
        }

        results.push({
          ...doc,
          highlight
        });
      }
    }

    // Sort by title match (higher priority) then by level (doc-level first)
    results.sort((a, b) => {
      const aTitle = a.title.toLowerCase().includes(normalizedQuery) ? 0 : 1;
      const bTitle = b.title.toLowerCase().includes(normalizedQuery) ? 0 : 1;
      if (aTitle !== bTitle) return aTitle - bTitle;
      return a.level - b.level;
    });

    return results.slice(0, 20);
  }, [searchIndex]);

  return { search, loading, error, isReady: !!searchIndex };
}
