import React from 'react';

type AdmonitionType = 'note' | 'tip' | 'info' | 'warning' | 'danger';

interface AdmonitionProps {
  type?: AdmonitionType;
  title?: string;
  children: React.ReactNode;
}

const config: Record<AdmonitionType, { icon: string; color: string; bg: string; border: string }> = {
  note: {
    icon: 'edit_note',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30'
  },
  tip: {
    icon: 'lightbulb',
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/30'
  },
  info: {
    icon: 'info',
    color: 'text-cyan-400',
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30'
  },
  warning: {
    icon: 'warning',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30'
  },
  danger: {
    icon: 'error',
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30'
  }
};

export default function Admonition({ type = 'note', title, children }: AdmonitionProps) {
  const { icon, color, bg, border } = config[type];
  const displayTitle = title || type.charAt(0).toUpperCase() + type.slice(1);

  return (
    <div className={`my-4 rounded-lg border ${border} ${bg} overflow-hidden`}>
      <div className={`flex items-center gap-2 px-4 py-2 ${color} font-medium`}>
        <span className="material-symbols-outlined">{icon}</span>
        <span>{displayTitle}</span>
      </div>
      <div className="px-4 pb-4 text-text-secondary">
        {children}
      </div>
    </div>
  );
}

// Named exports for JSX component usage
export const Note = (props: Omit<AdmonitionProps, 'type'>) => <Admonition type="note" {...props} />;
export const Tip = (props: Omit<AdmonitionProps, 'type'>) => <Admonition type="tip" {...props} />;
export const Info = (props: Omit<AdmonitionProps, 'type'>) => <Admonition type="info" {...props} />;
export const Warning = (props: Omit<AdmonitionProps, 'type'>) => <Admonition type="warning" {...props} />;
export const Danger = (props: Omit<AdmonitionProps, 'type'>) => <Admonition type="danger" {...props} />;
