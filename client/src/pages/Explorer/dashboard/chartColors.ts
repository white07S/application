/**
 * Shared chart color palette for the Controls Portfolio Dashboard.
 *
 * Guidelines:
 * - Use `primary` as the default single-series color.
 * - For multi-series, pick sequentially from `SERIES` (max 6).
 * - Avoid red (#e60000) for data — reserve it only for error states.
 * - Keep charts visually calm: prefer teal/slate/blue tones.
 */

/** Primary chart color — teal/lagoon */
export const CHART_PRIMARY = '#008e97';

/** Secondary chart color — muted slate blue */
export const CHART_SECONDARY = '#64748b';

/** Ordered palette for multi-series charts (lines, grouped bars). */
export const CHART_SERIES = [
    '#008e97', // teal (primary)
    '#64748b', // slate
    '#6366f1', // indigo
    '#0ea5e9', // sky blue
    '#8b5cf6', // violet
    '#14b8a6', // light teal
] as const;

/** Ordered palette for categorical bar charts (functions, themes, attributes). */
export const CHART_CATEGORICAL = [
    '#008e97',
    '#64748b',
    '#6366f1',
    '#0ea5e9',
    '#8b5cf6',
    '#14b8a6',
    '#475569',
    '#7c3aed',
] as const;

/** Heatmap / pass-rate thresholds — green/amber/slate (no red). */
export const HEATMAP_HIGH = 'bg-emerald-100 text-emerald-700';   // >= 85%
export const HEATMAP_MID  = 'bg-amber-100 text-amber-700';       // >= 60%
export const HEATMAP_LOW  = 'bg-slate-100 text-slate-600';        // < 60%
