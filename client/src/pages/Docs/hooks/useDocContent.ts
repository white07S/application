import { useState, useEffect } from 'react';
import { appConfig } from '../../../config/appConfig';

interface DocContentResult {
  content: string | null;
  loading: boolean;
  error: string | null;
}

export function useDocContent(slug: string): DocContentResult {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) {
      setLoading(false);
      return;
    }

    async function fetchContent() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${appConfig.api.baseUrl}/api/docs/content/${slug}`);
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Document not found');
          }
          throw new Error('Failed to fetch document content');
        }
        const text = await response.text();
        setContent(text);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setContent(null);
      } finally {
        setLoading(false);
      }
    }

    fetchContent();
  }, [slug]);

  return { content, loading, error };
}
