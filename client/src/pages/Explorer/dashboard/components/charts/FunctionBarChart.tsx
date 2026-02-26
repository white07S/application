import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart, CategoryScale, LinearScale, BarElement, Tooltip } from 'chart.js';
import { CHART_PRIMARY } from '../../chartColors';

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip);

interface FunctionBarChartProps {
    items: { name: string; value: number }[];
    color?: string;
    height?: number;
    valueLabel?: string;
}

const FunctionBarChart: React.FC<FunctionBarChartProps> = ({
    items,
    color = CHART_PRIMARY,
    height = 220,
    valueLabel = 'Controls',
}) => {
    const truncate = (s: string, max: number) => s.length > max ? s.slice(0, max) + '...' : s;

    return (
        <div style={{ height }}>
            <Bar
                data={{
                    labels: items.map(i => truncate(i.name, 25)),
                    datasets: [{
                        label: valueLabel,
                        data: items.map(i => i.value),
                        backgroundColor: color,
                        borderRadius: 2,
                        maxBarThickness: 16,
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
                                title: (ctx) => items[ctx[0].dataIndex]?.name || '',
                                label: (item) => `${(item.raw as number).toLocaleString()} ${valueLabel.toLowerCase()}`,
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

export default FunctionBarChart;
