/**
 * Converts Explorer sidebar's AppliedSidebarFilters to dashboard API payload.
 */

import { useMemo } from 'react';
import type { AppliedSidebarFilters } from '../../controls/types';
import type { DashboardFiltersPayload } from '../types';

export function buildDashboardFilters(
    applied: AppliedSidebarFilters,
): DashboardFiltersPayload {
    return {
        functions: applied.functions,
        locations: applied.locations,
        consolidated_entities: applied.consolidated_entities,
        assessment_units: applied.assessment_units,
        risk_themes: applied.risk_themes,
        filter_logic: applied.filterLogic,
        relationship_scope: applied.relationshipScope,
    };
}

export function useDashboardFilters(applied: AppliedSidebarFilters): DashboardFiltersPayload {
    return useMemo(() => buildDashboardFilters(applied), [applied]);
}
