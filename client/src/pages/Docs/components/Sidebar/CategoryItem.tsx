import React, { useState, useEffect } from 'react';
import type { Category } from '../../types';
import DocLink from './DocLink';

interface CategoryItemProps {
  category: Category;
  currentSlug: string;
}

export default function CategoryItem({ category, currentSlug }: CategoryItemProps) {
  const hasActiveItem = category.items.some(item => item.slug === currentSlug);
  const [isExpanded, setIsExpanded] = useState(hasActiveItem);

  // Expand when an item becomes active
  useEffect(() => {
    if (hasActiveItem) {
      setIsExpanded(true);
    }
  }, [hasActiveItem]);

  return (
    <div className="mb-2">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`
          w-full flex items-center gap-2 py-2 px-3 text-sm font-medium rounded-md
          transition-colors hover:bg-surface-alt/50
          ${hasActiveItem ? 'text-primary' : 'text-text-primary'}
        `}
      >
        <span className="material-symbols-outlined text-lg">
          {category.icon}
        </span>
        <span className="flex-1 text-left">{category.label}</span>
        <span className={`material-symbols-outlined text-base transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
          chevron_right
        </span>
      </button>

      {isExpanded && (
        <div className="ml-4 mt-1 border-l border-border pl-2">
          {category.items.map(item => (
            <DocLink
              key={item.slug}
              item={item}
              isActive={item.slug === currentSlug}
            />
          ))}
        </div>
      )}
    </div>
  );
}
