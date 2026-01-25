import { visit } from 'unist-util-visit';
import matter from 'gray-matter';
import GithubSlugger from 'github-slugger';
import type { Root, Heading, Paragraph, Code, List, Blockquote, Table } from 'mdast';
import { parseContent, extractText } from './parser.js';
import type { Frontmatter, ExtractedHeading, ParsedDocument } from './types.js';

/**
 * Extract frontmatter from file content
 */
export function extractFrontmatter(content: string): { frontmatter: Frontmatter; content: string } {
  const { data, content: body } = matter(content);
  return {
    frontmatter: data as Frontmatter,
    content: body
  };
}

/**
 * Extract all headings from AST
 */
export function extractHeadings(ast: Root): ExtractedHeading[] {
  const slugger = new GithubSlugger();
  const headings: ExtractedHeading[] = [];

  visit(ast, 'heading', (node: Heading) => {
    const text = extractText(node);
    if (text) {
      headings.push({
        text,
        level: node.depth,
        slug: slugger.slug(text)
      });
    }
  });

  return headings;
}

/**
 * Extract content text from various node types
 */
function extractNodeContent(node: unknown): string {
  if (!node || typeof node !== 'object') return '';

  const n = node as { type?: string; value?: string; children?: unknown[] };

  switch (n.type) {
    case 'paragraph':
    case 'heading':
      return extractText(node);
    case 'code':
      return (node as Code).value || '';
    case 'blockquote':
      return (n.children || []).map(child => extractNodeContent(child)).join(' ');
    case 'list':
      return (n.children || []).map(child => extractNodeContent(child)).join(' ');
    case 'listItem':
      return (n.children || []).map(child => extractNodeContent(child)).join(' ');
    case 'table':
      return extractTableContent(node as Table);
    default:
      if (n.children) {
        return (n.children as unknown[]).map(child => extractNodeContent(child)).join(' ');
      }
      return typeof n.value === 'string' ? n.value : '';
  }
}

/**
 * Extract text from table cells
 */
function extractTableContent(table: Table): string {
  const texts: string[] = [];
  for (const row of table.children) {
    for (const cell of row.children) {
      texts.push(extractText(cell));
    }
  }
  return texts.join(' ');
}

/**
 * Extract sections from content (split by headings)
 */
export function extractSections(ast: Root): { heading: ExtractedHeading | null; content: string }[] {
  const slugger = new GithubSlugger();
  const sections: { heading: ExtractedHeading | null; content: string }[] = [];

  let currentHeading: ExtractedHeading | null = null;
  let currentContent: string[] = [];

  function pushSection() {
    if (currentContent.length > 0 || currentHeading) {
      sections.push({
        heading: currentHeading,
        content: currentContent.join(' ').replace(/\s+/g, ' ').trim()
      });
    }
  }

  for (const node of ast.children) {
    if (node.type === 'heading') {
      pushSection();
      const text = extractText(node);
      currentHeading = {
        text,
        level: (node as Heading).depth,
        slug: slugger.slug(text)
      };
      currentContent = [];
    } else if (node.type === 'yaml') {
      // Skip frontmatter
      continue;
    } else {
      const text = extractNodeContent(node);
      if (text) {
        currentContent.push(text);
      }
    }
  }

  pushSection();
  return sections;
}

/**
 * Parse a complete document
 */
export function parseDocument(
  content: string,
  filePath: string,
  relativePath: string
): ParsedDocument {
  const { frontmatter, content: body } = extractFrontmatter(content);
  const ast = parseContent(body);
  const headings = extractHeadings(ast);
  const sections = extractSections(ast);

  return {
    filePath,
    relativePath,
    frontmatter,
    headings,
    content: body,
    sections
  };
}
