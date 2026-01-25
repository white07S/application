// Route types
export interface DocItem {
  slug: string;
  title: string;
  description?: string;
  sidebarPosition: number;
  filePath: string;
}

export interface Category {
  id: string;
  label: string;
  icon: string;
  position: number;
  items: DocItem[];
}

export interface DocsRoutes {
  version: string;
  generatedAt: string;
  defaultDoc: string;
  categories: Category[];
}

// Search index types
export interface SearchDocument {
  id: string;
  headingId: string;
  title: string;
  content: string;
  path: string;
  anchor: string;
  level: number;
  category: string;
  docTitle: string;
}

export interface SearchIndex {
  version: string;
  generatedAt: string;
  documents: SearchDocument[];
}

// Frontmatter types
export interface Frontmatter {
  title?: string;
  description?: string;
  sidebar_position?: number;
  sidebar_label?: string;
  [key: string]: unknown;
}

// Heading types
export interface ExtractedHeading {
  text: string;
  level: number;
  slug: string;
}

// Parsed document
export interface ParsedDocument {
  filePath: string;
  relativePath: string;
  frontmatter: Frontmatter;
  headings: ExtractedHeading[];
  content: string;
  sections: {
    heading: ExtractedHeading | null;
    content: string;
  }[];
}

// Category icon mapping
export const categoryIcons: Record<string, string> = {
  'getting-started': 'rocket_launch',
  'core-concepts': 'school',
  'api-reference': 'api',
  'models': 'psychology',
  'test-pages': 'science'
};

// Default positions for categories
export const categoryPositions: Record<string, number> = {
  'getting-started': 1,
  'core-concepts': 2,
  'api-reference': 3,
  'models': 4,
  'test-pages': 99
};

// Helper to convert slug to label
export function slugToLabel(slug: string): string {
  return slug
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
