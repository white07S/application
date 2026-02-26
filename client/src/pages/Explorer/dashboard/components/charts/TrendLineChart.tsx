import React from 'react';
import { Line } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend } from 'chart.js';

Chart.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

interface TrendLineChartProps {
    labels: string[];
    datasets: {
        label: string;
        data: (number | null)[];
        color: string;
    }[];
    yAxisLabel?: string;
    height?: number;
}

const TrendLineChart: React.FC<TrendLineChartProps> = ({
    labels,
    datasets,
    yAxisLabel,
    height = 220,
}) => (
    <div style={{ height }}>
        <Line
            data={{
                labels,
                datasets: datasets.map(ds => ({
                    label: ds.label,
                    data: ds.data,
                    borderColor: ds.color,
                    backgroundColor: ds.color + '20',
                    borderWidth: 1.5,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    tension: 0.3,
                    fill: false,
                    spanGaps: true,
                })),
            }}
            options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { font: { size: 10 }, boxWidth: 12, padding: 8 },
                    },
                },
                scales: {
                    x: {
                        ticks: { font: { size: 9 }, maxRotation: 45 },
                        grid: { display: false },
                    },
                    y: {
                        title: yAxisLabel ? { display: true, text: yAxisLabel, font: { size: 10 } } : undefined,
                        ticks: { font: { size: 9 } },
                        beginAtZero: true,
                    },
                },
            }}
        />
    </div>
);

export default TrendLineChart;
