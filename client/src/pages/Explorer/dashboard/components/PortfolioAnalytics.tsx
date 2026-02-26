import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, BarElement, Tooltip } from 'chart.js';
import type { PortfolioAnalyticsData } from '../types';
import { CHART_PRIMARY, CHART_SERIES } from '../chartColors';
import SummaryCard from './cards/SummaryCard';
import AttributeBarChart from './charts/AttributePieChart';
import FunctionBarChart from './charts/FunctionBarChart';
import ScoreDistributionChart from './charts/ScoreDistributionChart';

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip);

interface PortfolioAnalyticsProps {
    data: PortfolioAnalyticsData;
}

const PortfolioAnalytics: React.FC<PortfolioAnalyticsProps> = ({ data }) => {
    const attribute_distributions = data.attribute_distributions ?? [];
    const function_breakdown = data.function_breakdown ?? [];
    const risk_theme_breakdown = data.risk_theme_breakdown ?? [];
    const controls_created_by_month = data.controls_created_by_month ?? {};
    const controls_modified_by_month = data.controls_modified_by_month ?? {};

    const manualAutoDist = attribute_distributions.find(d => d.field === 'manual_automated');
    const execFreqDist = attribute_distributions.find(d => d.field === 'execution_frequency');
    const prevDetDist = attribute_distributions.find(d => d.field === 'preventative_detective');

    return (
        <div className="space-y-4">
            {/* Attribute Distributions */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                {manualAutoDist && (
                    <SummaryCard title="Automation Level" icon="precision_manufacturing">
                        <AttributeBarChart values={manualAutoDist.values} />
                    </SummaryCard>
                )}
                {prevDetDist && (
                    <SummaryCard title="Preventative vs Detective" icon="shield">
                        <AttributeBarChart values={prevDetDist.values} />
                    </SummaryCard>
                )}
                {execFreqDist && (
                    <SummaryCard title="Execution Frequency" icon="schedule">
                        <ScoreDistributionChart
                            distribution={execFreqDist.values}
                            maxScore={Object.keys(execFreqDist.values).length - 1}
                            label="Controls"
                            color={CHART_SERIES[2]}
                        />
                    </SummaryCard>
                )}
            </div>

            {/* Function & Risk Theme Breakdowns */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <SummaryCard title="Controls by Function" icon="apartment">
                    <FunctionBarChart
                        items={function_breakdown.slice(0, 15).map(f => ({ name: f.name, value: f.control_count }))}
                        height={Math.max(200, Math.min(function_breakdown.length, 15) * 22)}
                    />
                </SummaryCard>

                <SummaryCard title="Controls by Risk Theme" icon="category">
                    <FunctionBarChart
                        items={risk_theme_breakdown.slice(0, 15).map(t => ({ name: t.name, value: t.control_count }))}
                        color={CHART_SERIES[2]}
                        height={Math.max(200, Math.min(risk_theme_breakdown.length, 15) * 22)}
                    />
                </SummaryCard>
            </div>

            {/* Timeline: Created & Modified by Month */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                {Object.keys(controls_created_by_month).length > 0 && (
                    <SummaryCard title="Controls Created by Month" icon="add_circle">
                        <TimelineBarChart data={controls_created_by_month} color={CHART_SERIES[0]} label="Created" />
                    </SummaryCard>
                )}
                {Object.keys(controls_modified_by_month).length > 0 && (
                    <SummaryCard title="Controls Modified by Month" icon="edit_calendar">
                        <TimelineBarChart data={controls_modified_by_month} color={CHART_SERIES[1]} label="Modified" />
                    </SummaryCard>
                )}
            </div>
        </div>
    );
};

const TimelineBarChart: React.FC<{ data: Record<string, number>; color: string; label: string }> = ({ data, color, label }) => {
    const sorted = Object.entries(data).sort(([a], [b]) => a.localeCompare(b));
    return (
        <div style={{ height: 200 }}>
            <Bar
                data={{
                    labels: sorted.map(([k]) => k),
                    datasets: [{
                        label,
                        data: sorted.map(([, v]) => v),
                        backgroundColor: color,
                        borderRadius: 2,
                        maxBarThickness: 20,
                    }],
                }}
                options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (item) => `${(item.raw as number).toLocaleString()} controls`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            ticks: { font: { size: 9 }, maxRotation: 45 },
                            grid: { display: false },
                        },
                        y: {
                            ticks: { font: { size: 9 } },
                            beginAtZero: true,
                        },
                    },
                }}
            />
        </div>
    );
};

export default PortfolioAnalytics;
