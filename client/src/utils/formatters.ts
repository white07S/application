/**
 * Shared formatting utility functions.
 */

/**
 * Format bytes to human-readable size (B, KB, MB).
 */
export function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Format a date string to relative time (e.g., "5m ago", "2h ago").
 */
export function formatRelativeDate(isoString: string): string {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

/**
 * Format a date string to locale-specific string.
 */
export function formatDate(isoString: string): string {
    return new Date(isoString).toLocaleString();
}

/**
 * Format duration in seconds to human-readable string.
 */
export function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
}

/**
 * Get Tailwind color classes for data type badges.
 */
export function getDataTypeColor(dataType: string): string {
    switch (dataType) {
        case 'issues': return 'text-amber-600 bg-amber-50 border-amber-200';
        case 'controls': return 'text-blue-600 bg-blue-50 border-blue-200';
        case 'actions': return 'text-green-600 bg-green-50 border-green-200';
        default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
}

