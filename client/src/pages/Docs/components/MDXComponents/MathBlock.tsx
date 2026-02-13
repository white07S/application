import React from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

interface MathBlockProps {
  children: string;
  display?: boolean;
}

export default function MathBlock({ children, display = true }: MathBlockProps) {
  const math = children.trim();

  try {
    const html = katex.renderToString(math, {
      displayMode: display,
      throwOnError: false,
      errorColor: '#ef4444',
      trust: true,
      strict: false
    });

    return (
      <div
        className={`overflow-x-auto ${display ? 'my-4 py-2' : 'inline'}`}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  } catch (error) {
    console.error('KaTeX error:', error);
    return (
      <div className="my-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
        <p className="text-red-400 text-sm">Failed to render math expression</p>
        <pre className="mt-2 text-xs text-text-tertiary">{math}</pre>
      </div>
    );
  }
}

