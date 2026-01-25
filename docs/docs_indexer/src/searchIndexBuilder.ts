import path from 'path';
import type { ParsedDocument, SearchIndex, SearchDocument } from './types.js';
import { slugToLabel } from './types.js';

/**
 * Truncate content to max length, breaking at word boundaries
 */
function truncateContent(content: string, maxLength: number = 500): string {
  if (content.length <= maxLength) return content;

  const truncated = content.substring(0, maxLength);
  const lastSpace = truncated.lastIndexOf(' ');

  if (lastSpace > maxLength * 0.8) {
    return truncated.substring(0, lastSpace) + '...';
  }

  return truncated + '...';
}

/**
 * Build slug from relative path
 */
function buildSlug(relativePath: string): string {
  return relativePath
    .replace(/\.(md|mdx)$/, '')
    .replace(/\\/g, '/')
    .replace(/\/index$/, '');
}

/**
 * Extract category from path
 */
function extractCategory(relativePath: string): string {
  const parts = relativePath.split('/');
  if (parts.length > 1) {
    return slugToLabel(parts[0]);
  }
  return 'Overview';
}

/**
 * Build search index from parsed documents
 */
export function buildSearchIndex(documents: ParsedDocument[]): SearchIndex {
  const searchDocuments: SearchDocument[] = [];
  let docIndex = 0;

  for (const doc of documents) {
    const slug = buildSlug(doc.relativePath);
    const basePath = `/docs/${slug}`;
    const category = extractCategory(doc.relativePath);
    const docTitle = doc.frontmatter.title || slugToLabel(path.basename(slug));

    // Skip index if needed
    if (slug === 'index') {
      continue;
    }

    // Add document-level entry (description or first paragraph)
    const docContent = doc.frontmatter.description ||
      (doc.sections.find(s => !s.heading)?.content) ||
      '';

    if (docContent) {
      searchDocuments.push({
        id: `doc-${docIndex++}`,
        headingId: '',
        title: docTitle,
        content: truncateContent(docContent),
        path: basePath,
        anchor: basePath,
        level: 0,
        category,
        docTitle
      });
    }

    // Add section entries
    for (const section of doc.sections) {
      if (section.heading && section.content) {
        searchDocuments.push({
          id: `doc-${docIndex++}`,
          headingId: section.heading.slug,
          title: section.heading.text,
          content: truncateContent(section.content),
          path: basePath,
          anchor: `${basePath}#${section.heading.slug}`,
          level: section.heading.level,
          category,
          docTitle
        });
      }
    }
  }

  return {
    version: '1.0.0',
    generatedAt: new Date().toISOString(),
    documents: searchDocuments
  };
}
