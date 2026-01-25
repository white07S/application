import React from 'react';
import { Link } from 'react-router-dom';

interface BreadcrumbProps {
  category?: string;
  title: string;
}

export default function Breadcrumb({ category, title }: BreadcrumbProps) {
  return (
    <nav className="flex items-center gap-2 text-xs font-medium text-text-tertiary mb-4">
      <Link to="/docs" className="hover:text-text-secondary transition-colors">
        DOCS
      </Link>
      {category && (
        <>
          <span className="material-symbols-outlined text-sm">chevron_right</span>
          <span className="text-text-secondary uppercase">{category}</span>
        </>
      )}
      <span className="material-symbols-outlined text-sm">chevron_right</span>
      <span className="text-text-primary uppercase">{title}</span>
    </nav>
  );
}
