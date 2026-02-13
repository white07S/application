import React from 'react';

interface PaginationProps {
    page: number;
    totalPages: number;
    pageSize: number;
    total: number;
    onPageChange: (page: number) => void;
    onPageSizeChange: (size: number) => void;
}

const Pagination: React.FC<PaginationProps> = ({
    page,
    totalPages,
    pageSize,
    total,
    onPageChange,
    onPageSizeChange,
}) => {
    const start = (page - 1) * pageSize + 1;
    const end = Math.min(page * pageSize, total);

    return (
        <div className="flex items-center justify-between px-3 py-2 border-t border-border-light bg-surface-light/50">
            <div className="flex items-center gap-2 text-xs text-text-sub">
                <span>{start}-{end} of {total}</span>
                <span className="text-border-light">|</span>
                <label className="flex items-center gap-1">
                    Rows:
                    <select
                        value={pageSize}
                        onChange={(e) => onPageSizeChange(Number(e.target.value))}
                        className="px-1 py-0.5 border border-border-light rounded text-xs bg-white"
                    >
                        <option value={25}>25</option>
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                    </select>
                </label>
            </div>
            <div className="flex items-center gap-1">
                <button
                    onClick={() => onPageChange(1)}
                    disabled={page <= 1}
                    className="px-2 py-1 text-xs rounded border border-border-light bg-white hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    title="First page"
                >
                    <span className="material-symbols-outlined text-[14px]">first_page</span>
                </button>
                <button
                    onClick={() => onPageChange(page - 1)}
                    disabled={page <= 1}
                    className="px-2 py-1 text-xs rounded border border-border-light bg-white hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                    <span className="material-symbols-outlined text-[14px]">chevron_left</span>
                </button>
                <span className="px-2 py-1 text-xs text-text-sub">
                    {page} / {totalPages}
                </span>
                <button
                    onClick={() => onPageChange(page + 1)}
                    disabled={page >= totalPages}
                    className="px-2 py-1 text-xs rounded border border-border-light bg-white hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                    <span className="material-symbols-outlined text-[14px]">chevron_right</span>
                </button>
                <button
                    onClick={() => onPageChange(totalPages)}
                    disabled={page >= totalPages}
                    className="px-2 py-1 text-xs rounded border border-border-light bg-white hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    title="Last page"
                >
                    <span className="material-symbols-outlined text-[14px]">last_page</span>
                </button>
            </div>
        </div>
    );
};

export default Pagination;
