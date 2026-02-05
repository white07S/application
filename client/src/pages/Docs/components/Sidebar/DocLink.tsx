import React from 'react';
import { Link } from 'react-router-dom';
import type { DocItem } from '../../types';

interface DocLinkProps {
  item: DocItem;
  isActive: boolean;
}

export default function DocLink({ item, isActive }: DocLinkProps) {
  return (
    <Link
      to={`/docs/${item.slug}`}
      className={`
        block py-1.5 px-3 text-xs rounded transition-colors
        ${isActive
          ? 'bg-primary/10 text-primary font-medium'
          : 'text-text-secondary hover:text-text-primary hover:bg-surface-alt/50'
        }
      `}
    >
      {item.title}
    </Link>
  );
}
