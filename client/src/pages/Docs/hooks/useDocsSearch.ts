import { useState, useEffect, useCallback } from 'react';
import type { SearchIndex, SearchDocument } from '../types';
import { appConfig } from '../../../config/appConfig';

interface SearchResult extends SearchDocument {
  highlight?: string;
  score?: number;
}

// Pre-processed search index for faster lookups
interface ProcessedDocument extends SearchDocument {
  titleLower: string;
  contentLower: string;
}

interface ProcessedIndex {
  documents: ProcessedDocument[];
}

export function useDocsSearch() {
  const [searchIndex, setSearchIndex] = useState<ProcessedIndex | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchIndex() {
      try {
        const response = await fetch(`${appConfig.api.baseUrl}/api/docs/search-index`);
        if (!response.ok) {
          throw new Error('Failed to fetch search index');
        }
        const data: SearchIndex = await response.json();

        // Pre-process: store lowercase versions to avoid repeated conversions
        const processed: ProcessedIndex = {
          documents: data.documents.map(doc => ({
            ...doc,
            titleLower: doc.title.toLowerCase(),
            contentLower: doc.content.toLowerCase(),
          })),
        };
        setSearchIndex(processed);
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
    const maxResults = 20;

    // Collect matches with scores
    const scoredResults: Array<{ doc: ProcessedDocument; score: number }> = [];

    for (const doc of searchIndex.documents) {
      // Check if all terms match either title or content
      const matches = terms.every(term =>
        doc.titleLower.includes(term) || doc.contentLower.includes(term)
      );

      if (matches) {
        // Calculate relevance score
        let score = 0;

        // Title matches are worth more
        const titleMatchesAll = terms.every(term => doc.titleLower.includes(term));
        if (titleMatchesAll) score += 100;

        // Exact title match is best
        if (doc.titleLower === normalizedQuery) score += 50;

        // Title starts with query
        if (doc.titleLower.startsWith(normalizedQuery)) score += 25;

        // Lower level (doc-level) docs are more important
        score += (5 - doc.level) * 5;

        // Count term occurrences (capped to avoid bias)
        for (const term of terms) {
          const titleCount = (doc.titleLower.match(new RegExp(term, 'g')) || []).length;
          const contentCount = Math.min((doc.contentLower.match(new RegExp(term, 'g')) || []).length, 5);
          score += titleCount * 10 + contentCount;
        }

        scoredResults.push({ doc, score });
      }
    }

    // Sort by score descending
    scoredResults.sort((a, b) => b.score - a.score);

    // Take top results and create highlights only for those
    const topResults = scoredResults.slice(0, maxResults);

    return topResults.map(({ doc, score }) => {
      // Create highlight snippet
      let highlight = doc.content;
      const firstTermIndex = doc.contentLower.indexOf(terms[0]);

      if (firstTermIndex !== -1) {
        const start = Math.max(0, firstTermIndex - 40);
        const end = Math.min(doc.content.length, firstTermIndex + terms[0].length + 80);
        highlight = (start > 0 ? '...' : '') +
                   doc.content.slice(start, end) +
                   (end < doc.content.length ? '...' : '');
      }

      // Return all SearchDocument fields plus highlight and score
      return {
        id: doc.id,
        headingId: doc.headingId,
        title: doc.title,
        content: doc.content,
        path: doc.path,
        anchor: doc.anchor,
        level: doc.level,
        category: doc.category,
        docTitle: doc.docTitle,
        highlight,
        score,
      };
    });
  }, [searchIndex]);

  return { search, loading, error, isReady: !!searchIndex };
}
