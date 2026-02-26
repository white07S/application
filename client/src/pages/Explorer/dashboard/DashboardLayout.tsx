import React from 'react';
import type { AppliedSidebarFilters } from '../controls/types';
import type {
    DashboardTab,
    ExecutiveOverviewData,
    DocQualityData,
    PortfolioAnalyticsData,
    RegulatoryComplianceData,
} from './types';
import { useDashboardData } from './hooks/useDashboardData';
import ExecutiveOverview from './components/ExecutiveOverview';
import DocQualityMonitor from './components/DocQualityMonitor';
import HistoryTracking from './components/HistoryTracking';
import PortfolioAnalytics from './components/PortfolioAnalytics';
import RegulatoryCompliance from './components/RegulatoryCompliance';

interface DashboardLayoutProps {
    activeTab: DashboardTab;
    appliedFilters: AppliedSidebarFilters;
}

const BaseFilterBanner: React.FC = () => (
    <div className="flex items-center gap-2 px-3 py-1.5 mb-3 rounded bg-amber-50 border border-amber-200/60 text-[11px] text-amber-800">
        <span className="material-symbols-outlined text-[14px]">filter_alt</span>
        <span>
            Dashboard shows <strong>Active</strong> + <strong>Key Control</strong> only.
            Legacy and inactive controls are excluded from all calculations.
        </span>
    </div>
);

const DashboardLayout: React.FC<DashboardLayoutProps> = ({ activeTab, appliedFilters }) => {
    const { data, loading, error } = useDashboardData(activeTab, appliedFilters);

    if (activeTab === 'history') {
        return (
            <>
                <BaseFilterBanner />
                <HistoryTracking appliedFilters={appliedFilters} />
            </>
        );
    }

    if (loading) {
        return (
            <>
                <BaseFilterBanner />
                <div className="flex items-center justify-center h-40 text-text-sub">
                    <span className="material-symbols-outlined animate-spin text-[20px] mr-2">progress_activity</span>
                    <span className="text-xs">Loading dashboard data...</span>
                </div>
            </>
        );
    }

    if (error) {
        return (
            <>
                <BaseFilterBanner />
                <div className="flex items-center justify-center h-40 text-red-500">
                    <span className="material-symbols-outlined text-[20px] mr-2">error</span>
                    <span className="text-xs">{error}</span>
                </div>
            </>
        );
    }

    if (!data) {
        return (
            <>
                <BaseFilterBanner />
                <div className="flex items-center justify-center h-40 text-text-sub">
                    <span className="material-symbols-outlined animate-spin text-[20px] mr-2">progress_activity</span>
                    <span className="text-xs">Loading dashboard data...</span>
                </div>
            </>
        );
    }

    const renderTab = () => {
        switch (activeTab) {
            case 'overview':
                return <ExecutiveOverview data={data as ExecutiveOverviewData} />;
            case 'doc-quality':
                return <DocQualityMonitor data={data as DocQualityData} />;
            case 'analytics':
                return <PortfolioAnalytics data={data as PortfolioAnalyticsData} />;
            case 'regulatory':
                return <RegulatoryCompliance data={data as RegulatoryComplianceData} />;
            default:
                return null;
        }
    };

    return (
        <>
            <BaseFilterBanner />
            {renderTab()}
        </>
    );
};

export default DashboardLayout;
