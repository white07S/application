/**
 * TypeScript types for the Controls Portfolio Dashboard API.
 * Mirrors the Pydantic models in server/explorer/dashboard/models.py.
 */

// ── Building Blocks ──────────────────────────────────────────────────────

export interface PortfolioSummary {
    total_controls: number;
    total_l1: number;
    total_l2: number;
    active_controls: number;
    inactive_controls: number;
    key_controls: number;
    sox_relevant: number;
    ccar_relevant: number;
    bcbs239_relevant: number;
}

export interface ScoreDistribution {
    distribution: Record<string, number>; // {"0": 150, "1": 200, ...}
    avg_score: number | null;
    median_score: number | null;
    total_assessed: number;
}

export interface CriterionPassRate {
    criterion: string;
    label: string;
    pass_rate: number; // 0.0 to 1.0
    pass_count: number;
    total_count: number;
}

export interface AttributeDistribution {
    field: string;
    values: Record<string, number>;
}

export interface FunctionBreakdown {
    node_id: string;
    name: string;
    control_count: number;
    avg_score: number | null;
    active_count: number;
}

export interface RiskThemeBreakdown {
    theme_id: string;
    name: string;
    control_count: number;
}

// ── Endpoint Response Types ──────────────────────────────────────────────

export interface ExecutiveOverviewData {
    summary: PortfolioSummary;
    total_all_controls: number;
    l1_score_dist: ScoreDistribution;
    l2_score_dist: ScoreDistribution;
    criterion_pass_rates: CriterionPassRate[];
    attribute_distributions: AttributeDistribution[];
    top_functions: FunctionBreakdown[];
    top_risk_themes: RiskThemeBreakdown[];
    snapshot_at: string | null;
}

export interface RegulatoryComplianceData {
    summary: PortfolioSummary;
    sox_controls: number;
    ccar_controls: number;
    bcbs239_controls: number;
    sox_by_function: FunctionBreakdown[];
    sox_score_dist: ScoreDistribution;
}

// ── Time-Series Types ────────────────────────────────────────────────────

export interface SnapshotTrendPoint {
    snapshot_at: string;
    upload_id: string | null;
    total_controls: number;
    active_controls: number;
    avg_l1_score: number | null;
    avg_l2_score: number | null;
    controls_scoring_full_marks: number | null;
    controls_scoring_zero: number | null;
    criterion_pass_rates: Record<string, number>;
}

export interface TrendData {
    points: SnapshotTrendPoint[];
    total_snapshots: number;
}

export interface ScoreTrendPoint {
    snapshot_at: string;
    distribution: Record<string, number>;
    avg_score: number | null;
}

export interface ScoreTrendData {
    l1_trend: ScoreTrendPoint[];
    l2_trend: ScoreTrendPoint[];
}

// ── Lifecycle Heatmap ────────────────────────────────────────────────────

export interface LifecycleMonthPoint {
    month: string; // "2025-01"
    created: number;
    retired: number;
}

export interface LifecycleHeatmapData {
    months: LifecycleMonthPoint[];
}

// ── Concentration (Who / Where Month-over-Month) ────────────────────────

export interface ConcentrationEntry {
    value: string;
    count: number;
}

export interface ConcentrationMonthPoint {
    month: string;
    top: ConcentrationEntry[];
    others_count: number;
}

export interface ConcentrationData {
    dimension: string;
    top_values: string[];
    months: ConcentrationMonthPoint[];
    grid: Record<string, Record<string, number>>;
}

// ── Similarity Redundancy Month-over-Month ──────────────────────────────

export interface RedundancyMonthPoint {
    month: string;
    total_created: number;
    with_prior_near_duplicate: number;
    with_prior_weak_similar: number;
    with_prior_similar: number;
    redundancy_pct: number;
}

export interface RedundancyData {
    months: RedundancyMonthPoint[];
}

// ── Dashboard UI Types ───────────────────────────────────────────────────

export type DashboardTab =
    | 'overview'
    | 'controls'
    | 'similarity'
    | 'history'
    | 'regulatory';

export interface DashboardFiltersPayload {
    functions: string[];
    locations: string[];
    consolidated_entities: string[];
    assessment_units: string[];
    risk_themes: string[];
    filter_logic: string;
    relationship_scope: string;
}
