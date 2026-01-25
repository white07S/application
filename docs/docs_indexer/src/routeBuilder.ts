import path from 'path';
import type { ParsedDocument, DocsRoutes, Category, DocItem } from './types.js';
import { categoryIcons, categoryPositions, slugToLabel } from './types.js';

/**
 * Build the slug from file path
 */
function buildSlug(relativePath: string): string {
  // Remove extension and normalize
  return relativePath
    .replace(/\.(md|mdx)$/, '')
    .replace(/\\/g, '/')
    .replace(/\/index$/, '');
}

/**
 * Extract category from path
 */
function extractCategory(relativePath: string): string | null {
  const parts = relativePath.split('/');
  if (parts.length > 1) {
    return parts[0];
  }
  return null;
}

/**
 * Build docs routes from parsed documents
 */
export function buildDocsRoutes(documents: ParsedDocument[]): DocsRoutes {
  const categoriesMap = new Map<string, Category>();
  const rootItems: DocItem[] = [];

  for (const doc of documents) {
    const slug = buildSlug(doc.relativePath);
    const categoryId = extractCategory(doc.relativePath);

    // Skip index.mdx - it's handled as default doc
    if (slug === 'index' || doc.relativePath === 'index.mdx') {
      continue;
    }

    const docItem: DocItem = {
      slug,
      title: doc.frontmatter.title || doc.frontmatter.sidebar_label || slugToLabel(path.basename(slug)),
      description: doc.frontmatter.description,
      sidebarPosition: doc.frontmatter.sidebar_position ?? 999,
      filePath: doc.relativePath
    };

    if (categoryId) {
      if (!categoriesMap.has(categoryId)) {
        categoriesMap.set(categoryId, {
          id: categoryId,
          label: slugToLabel(categoryId),
          icon: categoryIcons[categoryId] || 'folder',
          position: categoryPositions[categoryId] ?? 50,
          items: []
        });
      }
      categoriesMap.get(categoryId)!.items.push(docItem);
    } else {
      rootItems.push(docItem);
    }
  }

  // Sort items within each category
  for (const category of categoriesMap.values()) {
    category.items.sort((a, b) => a.sidebarPosition - b.sidebarPosition);
  }

  // Convert to array and sort categories
  const categories = Array.from(categoriesMap.values()).sort(
    (a, b) => a.position - b.position
  );

  // Add root items as a special category if any exist
  if (rootItems.length > 0) {
    rootItems.sort((a, b) => a.sidebarPosition - b.sidebarPosition);
    categories.unshift({
      id: 'root',
      label: 'Overview',
      icon: 'home',
      position: 0,
      items: rootItems
    });
  }

  return {
    version: '1.0.0',
    generatedAt: new Date().toISOString(),
    defaultDoc: 'getting-started/introduction',
    categories
  };
}
