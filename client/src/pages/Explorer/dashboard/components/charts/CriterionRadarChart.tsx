import React from 'react';
import { Radar } from 'react-chartjs-2';
import { Chart, RadialLinearScale, PointElement, LineElement, Filler, Tooltip } from 'chart.js';
import type { CriterionPassRate } from '../../types';
import { CHART_PRIMARY } from '../../chartColors';

Chart.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip);

interface CriterionRadarChartProps {
    criteria: CriterionPassRate[];
    height?: number;
}

const CriterionRadarChart: React.FC<CriterionRadarChartProps> = ({ criteria, height = 260 }) => {
    const labels = criteria.map(c => c.label);
    const data = criteria.map(c => Math.round(c.pass_rate * 100));

    return (
        <div style={{ height }}>
            <Radar
                data={{
                    labels,
                    datasets: [{
                        label: 'Pass Rate %',
                        data,
                        backgroundColor: CHART_PRIMARY + '25',
                        borderColor: CHART_PRIMARY,
                        borderWidth: 1.5,
                        pointBackgroundColor: CHART_PRIMARY,
                        pointRadius: 3,
                    }],
                }}
                options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (item) => `${item.raw}%`,
                            },
                        },
                    },
                    scales: {
                        r: {
                            min: 0,
                            max: 100,
                            ticks: { stepSize: 25, font: { size: 8 }, backdropColor: 'transparent' },
                            pointLabels: { font: { size: 9 } },
                            grid: { color: 'rgba(0,0,0,0.06)' },
                        },
                    },
                }}
            />
        </div>
    );
};

export default CriterionRadarChart;
