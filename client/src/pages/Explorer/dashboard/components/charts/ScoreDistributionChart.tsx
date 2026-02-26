import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js';
import { CHART_PRIMARY } from '../../chartColors';

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

interface ScoreDistributionChartProps {
    distribution: Record<string, number>;
    maxScore: number;
    label: string;
    color?: string;
    height?: number;
}

const ScoreDistributionChart: React.FC<ScoreDistributionChartProps> = ({
    distribution,
    maxScore,
    label,
    color = CHART_PRIMARY,
    height = 200,
}) => {
    const labels = Array.from({ length: maxScore + 1 }, (_, i) => String(i));
    const data = labels.map(l => distribution[l] || 0);

    return (
        <div style={{ height }}>
            <Bar
                data={{
                    labels,
                    datasets: [{
                        label,
                        data,
                        backgroundColor: color,
                        borderRadius: 2,
                        maxBarThickness: 28,
                    }],
                }}
                options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (items) => `Score: ${items[0].label}`,
                                label: (item) => `${item.raw} controls`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            title: { display: true, text: 'Score', font: { size: 10 } },
                            ticks: { font: { size: 9 } },
                            grid: { display: false },
                        },
                        y: {
                            title: { display: true, text: 'Controls', font: { size: 10 } },
                            ticks: { font: { size: 9 } },
                            beginAtZero: true,
                        },
                    },
                }}
            />
        </div>
    );
};

export default ScoreDistributionChart;
