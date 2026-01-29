import React from 'react';
import { Code, Bug } from 'lucide-react';
import { useActiveHeading } from '../../hooks/useActiveHeading';
import type { TocHeading } from '../../types';

interface TableOfContentsProps {
  headings: TocHeading[];
}

export default function TableOfContents({ headings }: TableOfContentsProps) {
  const activeId = useActiveHeading(headings);

  // Filter to show only h2 and h3
  const visibleHeadings = headings.filter(h => h.level >= 2 && h.level <= 3);

  if (visibleHeadings.length === 0) {
    return null;
  }

  return (
    <aside className="w-64 xl:w-72 2xl:w-80 shrink-0 hidden xl:block">
      <div className="sticky top-20 overflow-y-auto max-h-[calc(100vh-6rem)]">
        <div className="pl-4 border-l border-border">
          <h4 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">
            On This Page
          </h4>
          <nav className="space-y-1">
            {visibleHeadings.map(heading => (
              <a
                key={heading.id}
                href={`#${heading.id}`}
                className={`
                  block py-1.5 min-h-[32px] text-sm transition-colors
                  ${heading.level === 3 ? 'pl-3' : ''}
                  ${activeId === heading.id
                    ? 'text-primary font-medium'
                    : 'text-text-tertiary hover:text-text-secondary'
                  }
                `}
              >
                {heading.text}
              </a>
            ))}
          </nav>

          {/* Resources section */}
          <div className="mt-8 pt-4 border-t border-border">
            <h4 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">
              Resources
            </h4>
            <nav className="space-y-2">
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 py-1.5 min-h-[32px] text-sm text-text-tertiary hover:text-text-secondary transition-colors"
              >
                <Code className="w-4 h-4 shrink-0" />
                View Source
              </a>
              <a
                href="#"
                className="flex items-center gap-2 py-1.5 min-h-[32px] text-sm text-text-tertiary hover:text-text-secondary transition-colors"
              >
                <Bug className="w-4 h-4 shrink-0" />
                Report Issue
              </a>
            </nav>
          </div>
        </div>
      </div>
    </aside>
  );
}
