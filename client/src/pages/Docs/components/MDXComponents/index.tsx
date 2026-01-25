import React from 'react';
import { Link } from 'react-router-dom';
import { H1, H2, H3, H4, H5, H6 } from './Heading';
import CodeBlock from './CodeBlock';
import { Note, Tip, Info, Warning, Danger } from './Admonition';
import MermaidDiagram from './MermaidDiagram';
import MathBlock from './MathBlock';
import { Table, TableHead, TableBody, TableRow, TableHeader, TableCell } from './Table';

// Helper to extract text from children recursively
function extractTextContent(node: React.ReactNode): string {
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (node == null) return '';

  if (Array.isArray(node)) {
    return node.map(extractTextContent).join('');
  }

  if (React.isValidElement(node)) {
    const props = node.props as Record<string, unknown>;
    if (props.children) {
      return extractTextContent(props.children as React.ReactNode);
    }
  }

  return '';
}

// Pre component to handle code blocks
interface PreProps {
  children?: React.ReactNode;
  [key: string]: unknown;
}

function Pre({ children }: PreProps) {
  // Handle the children to extract code content and language
  let codeContent = '';
  let language = '';

  React.Children.forEach(children, (child) => {
    if (React.isValidElement(child)) {
      const childProps = child.props as Record<string, unknown>;

      // Extract className for language detection
      if (typeof childProps.className === 'string') {
        const langMatch = childProps.className.match(/language-(\w+)/);
        if (langMatch) {
          language = langMatch[1];
        }
      }

      // Extract the actual code content
      if (childProps.children) {
        codeContent = extractTextContent(childProps.children as React.ReactNode);
      }
    } else if (typeof child === 'string') {
      codeContent = child;
    }
  });

  // If no code content was found, try direct children
  if (!codeContent) {
    codeContent = extractTextContent(children);
  }

  // Trim the code
  codeContent = codeContent.trim();

  if (!codeContent) {
    return <pre>{children}</pre>;
  }

  // Handle mermaid diagrams
  if (language === 'mermaid') {
    return <MermaidDiagram chart={codeContent} />;
  }

  // Regular code block with syntax highlighting
  return (
    <CodeBlock className={language ? `language-${language}` : ''}>
      {codeContent}
    </CodeBlock>
  );
}

// Code component - only for inline code (no className)
interface CodeProps {
  children?: React.ReactNode;
  className?: string;
  [key: string]: unknown;
}

function Code({ children, className, ...props }: CodeProps) {
  // If this has a language class, it's inside a pre block - render as-is
  // The Pre component will handle the styling
  if (className && className.includes('language-')) {
    return <code className={className} {...props}>{children}</code>;
  }

  // Inline code styling
  return (
    <code className="px-1.5 py-0.5 bg-surface-alt text-primary rounded text-sm font-mono" {...props}>
      {children}
    </code>
  );
}

// Anchor component for links
function Anchor({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  if (href?.startsWith('/')) {
    return (
      <Link
        to={href}
        className="text-primary hover:text-primary/80 underline underline-offset-2"
      >
        {children}
      </Link>
    );
  }

  if (href?.startsWith('#')) {
    return (
      <a
        href={href}
        className="text-primary hover:text-primary/80 underline underline-offset-2"
        {...props}
      >
        {children}
      </a>
    );
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary hover:text-primary/80 underline underline-offset-2 inline-flex items-center gap-1"
      {...props}
    >
      {children}
      <span className="material-symbols-outlined text-sm">open_in_new</span>
    </a>
  );
}

// Paragraph component
function Paragraph({ children }: { children: React.ReactNode }) {
  return <p className="my-4 leading-relaxed text-text-secondary">{children}</p>;
}

// List components
function UnorderedList({ children }: { children: React.ReactNode }) {
  return <ul className="my-4 pl-6 list-disc space-y-2 text-text-secondary">{children}</ul>;
}

function OrderedList({ children }: { children: React.ReactNode }) {
  return <ol className="my-4 pl-6 list-decimal space-y-2 text-text-secondary">{children}</ol>;
}

function ListItem({ children }: { children: React.ReactNode }) {
  return <li className="leading-relaxed">{children}</li>;
}

// Blockquote component
function Blockquote({ children }: { children: React.ReactNode }) {
  return (
    <blockquote className="my-4 pl-4 border-l-4 border-primary/50 italic text-text-secondary">
      {children}
    </blockquote>
  );
}

// Horizontal rule
function Hr() {
  return <hr className="my-8 border-border" />;
}

// Image component
function Image(props: React.ImgHTMLAttributes<HTMLImageElement>) {
  return (
    <img
      {...props}
      className="my-4 rounded-lg max-w-full h-auto"
      loading="lazy"
      alt={props.alt || ''}
    />
  );
}

// Strong and emphasis
function Strong({ children }: { children: React.ReactNode }) {
  return <strong className="font-semibold text-text-primary">{children}</strong>;
}

function Emphasis({ children }: { children: React.ReactNode }) {
  return <em className="italic">{children}</em>;
}

// Details/Summary for collapsible content
function Details({ children }: { children: React.ReactNode }) {
  return (
    <details className="my-4 rounded-lg border border-border overflow-hidden">
      {children}
    </details>
  );
}

function Summary({ children }: { children: React.ReactNode }) {
  return (
    <summary className="px-4 py-2 bg-surface-alt cursor-pointer font-medium hover:bg-surface-alt/80">
      {children}
    </summary>
  );
}

// Export all components
export const mdxComponents = {
  h1: H1,
  h2: H2,
  h3: H3,
  h4: H4,
  h5: H5,
  h6: H6,
  p: Paragraph,
  a: Anchor,
  pre: Pre,
  code: Code,
  table: Table,
  thead: TableHead,
  tbody: TableBody,
  tr: TableRow,
  th: TableHeader,
  td: TableCell,
  ul: UnorderedList,
  ol: OrderedList,
  li: ListItem,
  blockquote: Blockquote,
  hr: Hr,
  img: Image,
  strong: Strong,
  em: Emphasis,
  details: Details,
  summary: Summary,
  // Admonition components (for JSX in MDX)
  Note,
  Tip,
  Info,
  Warning,
  Danger,
  // Math component
  MathBlock
};

export default mdxComponents;
