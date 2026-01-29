import React from 'react';

interface TableProps {
  children: React.ReactNode;
}

export function Table({ children }: TableProps) {
  return (
    <div className="my-4 rounded-lg border border-border">
      <div
        className="table-scroll-container overflow-x-auto -mx-3 px-3"
        style={{ WebkitOverflowScrolling: 'touch' }}
      >
        <table className="min-w-full w-full text-sm">
          {children}
        </table>
      </div>
    </div>
  );
}

export function TableHead({ children }: { children: React.ReactNode }) {
  return (
    <thead className="bg-surface-alt border-b border-border">
      {children}
    </thead>
  );
}

export function TableBody({ children }: { children: React.ReactNode }) {
  return <tbody className="divide-y divide-border">{children}</tbody>;
}

export function TableRow({ children }: { children: React.ReactNode }) {
  return (
    <tr className="hover:bg-surface-alt/50 transition-colors">
      {children}
    </tr>
  );
}

export function TableHeader({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-4 py-3 text-left font-semibold text-text-primary">
      {children}
    </th>
  );
}

export function TableCell({ children }: { children: React.ReactNode }) {
  return (
    <td className="px-4 py-3 text-text-secondary">
      {children}
    </td>
  );
}
