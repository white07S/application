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

// Extracted heading for TOC
export interface TocHeading {
  id: string;
  text: string;
  level: number;
}

// Navigation context
export interface DocNavItem {
  slug: string;
  title: string;
  category: string;
}

export interface DocsNavigation {
  prev?: DocNavItem;
  next?: DocNavItem;
}
