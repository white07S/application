import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, BarElement, Tooltip } from 'chart.js';
import { CHART_CATEGORICAL } from '../../chartColors';

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip);

interface AttributeBarChartProps {
    values: Record<string, number>;
    height?: number;
}

const AttributeBarChart: React.FC<AttributeBarChartProps> = ({ values, height = 200 }) => {
    const entries = Object.entries(values).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
    const labels = entries.map(([k]) => k);
    const data = entries.map(([, v]) => v);
    const total = data.reduce((s, v) => s + v, 0);

    return (
        <div style={{ height }}>
            <Bar
                data={{
                    labels,
                    datasets: [{
                        label: 'Controls',
                        data,
                        backgroundColor: CHART_CATEGORICAL.slice(0, labels.length) as unknown as string[],
                        borderRadius: 2,
                        maxBarThickness: 18,
                    }],
                }}
                options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (item) => {
                                    const val = item.raw as number;
                                    const pct = total > 0 ? Math.round((val / total) * 100) : 0;
                                    return `${val.toLocaleString()} controls (${pct}%)`;
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            ticks: { font: { size: 9 } },
                            beginAtZero: true,
                        },
                        y: {
                            ticks: { font: { size: 9 } },
                            grid: { display: false },
                        },
                    },
                }}
            />
        </div>
    );
};

export default AttributeBarChart;
