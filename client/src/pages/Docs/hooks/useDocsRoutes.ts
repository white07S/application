import { useState, useEffect } from 'react';
import type { DocsRoutes, DocsNavigation, DocNavItem } from '../types';
import { appConfig } from '../../../config/appConfig';

export function useDocsRoutes() {
  const [routes, setRoutes] = useState<DocsRoutes | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchRoutes() {
      try {
        const response = await fetch(`${appConfig.api.baseUrl}/api/docs/routes`);
        if (!response.ok) {
          throw new Error('Failed to fetch documentation routes');
        }
        const data = await response.json();
        setRoutes(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }

    fetchRoutes();
  }, []);

  return { routes, loading, error };
}

export function useDocsNavigation(routes: DocsRoutes | null, currentSlug: string): DocsNavigation {
  if (!routes) return {};

  // Flatten all items with their category
  const allItems: DocNavItem[] = [];
  for (const category of routes.categories) {
    for (const item of category.items) {
      allItems.push({
        slug: item.slug,
        title: item.title,
        category: category.label
      });
    }
  }

  // Find current index
  const currentIndex = allItems.findIndex(item => item.slug === currentSlug);

  if (currentIndex === -1) return {};

  return {
    prev: currentIndex > 0 ? allItems[currentIndex - 1] : undefined,
    next: currentIndex < allItems.length - 1 ? allItems[currentIndex + 1] : undefined
  };
}
