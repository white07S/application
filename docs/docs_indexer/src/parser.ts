import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkFrontmatter from 'remark-frontmatter';
import type { Root } from 'mdast';

/**
 * Pre-process content to transform admonitions for output files
 * Converts :::type content ::: to JSX components
 */
export function preprocessAdmonitions(content: string): string {
  // Match admonition blocks: :::type optional-title\ncontent\n:::
  const admonitionRegex = /^:::(note|tip|info|warning|danger)(?:\s+(.+))?\n([\s\S]*?)^:::/gm;

  return content.replace(admonitionRegex, (_, type, title, innerContent) => {
    const componentName = type.charAt(0).toUpperCase() + type.slice(1);
    const trimmedContent = innerContent.trim();

    if (title) {
      return `<${componentName} title="${title.trim()}">\n${trimmedContent}\n</${componentName}>`;
    }
    return `<${componentName}>\n${trimmedContent}\n</${componentName}>`;
  });
}

/**
 * Create a unified processor for parsing markdown
 * Note: We use plain markdown parsing (not MDX) for the indexer
 * to avoid issues with math expressions and other special syntax.
 * MDX rendering is handled on the client side.
 */
export function createParser() {
  return unified()
    .use(remarkParse)
    .use(remarkFrontmatter, ['yaml'])
    .use(remarkGfm);
}

/**
 * Parse markdown content into an AST
 */
export function parseContent(content: string): Root {
  const parser = createParser();
  return parser.parse(content) as Root;
}

/**
 * Extract plain text from a node and its children
 */
export function extractText(node: unknown): string {
  if (!node || typeof node !== 'object') return '';

  const n = node as { type?: string; value?: string; children?: unknown[] };

  if (n.type === 'text' && typeof n.value === 'string') {
    return n.value;
  }

  if (Array.isArray(n.children)) {
    return n.children.map(child => extractText(child)).join('');
  }

  return '';
}
