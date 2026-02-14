import React from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description?: string;
}

const EmptyState: React.FC<EmptyStateProps> = ({ title, description }) => {
  return (
    <div className="flex h-full min-h-[220px] items-center justify-center rounded border border-dashed border-border-light bg-white px-4">
      <div className="text-center">
        <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-surface-light">
          <Inbox size={16} className="text-text-sub" />
        </div>
        <div className="text-sm font-medium text-text-main">{title}</div>
        {description && <div className="mt-1 text-xs text-text-sub">{description}</div>}
      </div>
    </div>
  );
};

export default EmptyState;

