import React, { useState } from 'react';
import { Highlight, themes } from 'prism-react-renderer';

interface CodeBlockProps {
  children: string;
  className?: string;
  title?: string;
  showLineNumbers?: boolean;
}

export default function CodeBlock({
  children,
  className = '',
  title,
  showLineNumbers = false
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  // Extract language from className (e.g., "language-javascript")
  const match = className.match(/language-(\w+)/);
  const language = match ? match[1] : 'text';

  // Ensure children is a string
  const code = (typeof children === 'string' ? children : String(children || '')).trim();

  if (!code) {
    return null;
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-4 rounded-lg overflow-hidden border border-border">
      {/* Header with language and copy button */}
      <div className="flex items-center justify-between px-4 py-2 bg-surface-alt border-b border-border">
        <span className="text-xs font-mono text-text-secondary uppercase">
          {title || language}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary transition-colors"
        >
          <span className="material-symbols-outlined text-base">
            {copied ? 'check' : 'content_copy'}
          </span>
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>

      {/* Code content - using light theme */}
      <Highlight
        theme={themes.github}
        code={code}
        language={language}
      >
        {({ className: hlClassName, style, tokens, getLineProps, getTokenProps }) => (
          <pre
            className={`${hlClassName} overflow-x-auto p-4 text-sm leading-relaxed`}
            style={{ ...style, margin: 0, background: '#f9f9f7' }}
          >
            {tokens.map((line, i) => (
              <div key={i} {...getLineProps({ line })} className="table-row">
                {showLineNumbers && (
                  <span className="table-cell pr-4 text-right select-none text-gray-400">
                    {i + 1}
                  </span>
                )}
                <span className="table-cell">
                  {line.map((token, key) => (
                    <span key={key} {...getTokenProps({ token })} />
                  ))}
                </span>
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  );
}
