import React from 'react';

interface HeadingProps {
  level: 1 | 2 | 3 | 4 | 5 | 6;
  id?: string;
  children: React.ReactNode;
}

const styles: Record<number, string> = {
  1: 'text-3xl font-bold mt-0 mb-6',
  2: 'text-2xl font-semibold mt-10 mb-4 pb-2 border-b border-border',
  3: 'text-xl font-semibold mt-8 mb-3',
  4: 'text-lg font-medium mt-6 mb-2',
  5: 'text-base font-medium mt-4 mb-2',
  6: 'text-sm font-medium mt-4 mb-2 text-text-secondary',
};

function createSlug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-');
}

export default function Heading({ level, id, children }: HeadingProps) {
  // Generate id from children text if not provided
  const headingId = id || (typeof children === 'string' ? createSlug(children) : undefined);
  const className = `${styles[level]} group relative`;

  const anchorLink = headingId && (
    <a
      href={`#${headingId}`}
      className="absolute -left-6 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100
                 text-text-tertiary hover:text-primary transition-opacity"
      aria-label="Link to this section"
    >
      <span className="material-symbols-outlined text-lg">#</span>
    </a>
  );

  switch (level) {
    case 1: return <h1 id={headingId} className={className}>{children}{anchorLink}</h1>;
    case 2: return <h2 id={headingId} className={className}>{children}{anchorLink}</h2>;
    case 3: return <h3 id={headingId} className={className}>{children}{anchorLink}</h3>;
    case 4: return <h4 id={headingId} className={className}>{children}{anchorLink}</h4>;
    case 5: return <h5 id={headingId} className={className}>{children}{anchorLink}</h5>;
    case 6: return <h6 id={headingId} className={className}>{children}{anchorLink}</h6>;
  }
}

// Create specific heading components for MDX
export const H1 = (props: React.HTMLAttributes<HTMLHeadingElement>) => (
  <Heading level={1} {...props}>{props.children}</Heading>
);

export const H2 = (props: React.HTMLAttributes<HTMLHeadingElement>) => (
  <Heading level={2} {...props}>{props.children}</Heading>
);

export const H3 = (props: React.HTMLAttributes<HTMLHeadingElement>) => (
  <Heading level={3} {...props}>{props.children}</Heading>
);

export const H4 = (props: React.HTMLAttributes<HTMLHeadingElement>) => (
  <Heading level={4} {...props}>{props.children}</Heading>
);

export const H5 = (props: React.HTMLAttributes<HTMLHeadingElement>) => (
  <Heading level={5} {...props}>{props.children}</Heading>
);

export const H6 = (props: React.HTMLAttributes<HTMLHeadingElement>) => (
  <Heading level={6} {...props}>{props.children}</Heading>
);
