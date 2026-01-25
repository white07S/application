import React, { useState, useEffect, useMemo } from 'react';
import { compile, run } from '@mdx-js/mdx';
import * as runtime from 'react/jsx-runtime';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import mdxComponents from '../MDXComponents';
import type { TocHeading } from '../../types';
import 'katex/dist/katex.min.css';

interface MDXRendererProps {
  content: string;
  onHeadingsExtracted?: (headings: TocHeading[]) => void;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type MDXComponent = React.ComponentType<{ components?: Record<string, React.ComponentType<any>> }>;

// Extract frontmatter and content
function parseFrontmatter(content: string): { frontmatter: Record<string, string>; body: string } {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);

  if (match) {
    const frontmatterStr = match[1];
    const body = match[2];

    const frontmatter: Record<string, string> = {};
    frontmatterStr.split('\n').forEach(line => {
      const colonIndex = line.indexOf(':');
      if (colonIndex !== -1) {
        const key = line.substring(0, colonIndex).trim();
        const value = line.substring(colonIndex + 1).trim().replace(/^["']|["']$/g, '');
        frontmatter[key] = value;
      }
    });

    return { frontmatter, body };
  }

  return { frontmatter: {}, body: content };
}

// Extract headings from content
function extractHeadings(content: string): TocHeading[] {
  const headings: TocHeading[] = [];
  const headingRegex = /^(#{1,6})\s+(.+)$/gm;
  let match;

  while ((match = headingRegex.exec(content)) !== null) {
    const level = match[1].length;
    const text = match[2].trim();
    const id = text
      .toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/\s+/g, '-');

    headings.push({ id, text, level });
  }

  return headings;
}

export default function MDXRenderer({ content, onHeadingsExtracted }: MDXRendererProps) {
  const [Component, setComponent] = useState<MDXComponent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { frontmatter, body } = useMemo(() => parseFrontmatter(content), [content]);

  // Extract headings and notify parent
  useEffect(() => {
    if (onHeadingsExtracted) {
      const headings = extractHeadings(body);
      onHeadingsExtracted(headings);
    }
  }, [body, onHeadingsExtracted]);

  useEffect(() => {
    async function compileMDX() {
      try {
        const compiled = await compile(body, {
          outputFormat: 'function-body',
          remarkPlugins: [remarkGfm, remarkMath],
          rehypePlugins: [rehypeKatex],
          development: false
        });

        const { default: MDXContent } = await run(String(compiled), {
          ...runtime,
          baseUrl: import.meta.url
        });

        setComponent(() => MDXContent);
        setError(null);
      } catch (err) {
        console.error('MDX compilation error:', err);
        setError(err instanceof Error ? err.message : 'Failed to compile MDX');
      }
    }

    if (body) {
      compileMDX();
    }
  }, [body]);

  if (error) {
    return (
      <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
        <h3 className="text-red-400 font-medium mb-2">Failed to render document</h3>
        <pre className="text-xs text-text-tertiary overflow-x-auto whitespace-pre-wrap">{error}</pre>
      </div>
    );
  }

  if (!Component) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-surface-alt rounded w-3/4" />
        <div className="h-4 bg-surface-alt rounded" />
        <div className="h-4 bg-surface-alt rounded w-5/6" />
        <div className="h-4 bg-surface-alt rounded w-4/5" />
      </div>
    );
  }

  return (
    <article className="docs-content">
      <Component components={mdxComponents} />
    </article>
  );
}
