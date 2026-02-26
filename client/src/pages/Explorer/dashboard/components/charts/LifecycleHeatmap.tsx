import React from 'react';
import type { LifecycleMonthPoint } from '../../types';
import { CHART_SERIES } from '../../chartColors';

interface LifecycleHeatmapProps {
    months: LifecycleMonthPoint[];
}

/** Map a count to an opacity level (0.0–1.0) based on the max value in the dataset. */
const intensity = (value: number, max: number): number => {
    if (max === 0 || value === 0) return 0;
    return Math.max(0.1, value / max);
};

const formatMonth = (month: string): string => {
    const [y, m] = month.split('-');
    const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${names[parseInt(m, 10) - 1]} ${y.slice(2)}`;
};

const LifecycleHeatmap: React.FC<LifecycleHeatmapProps> = ({ months }) => {
    const maxCreated = Math.max(...months.map(m => m.created), 1);
    const maxRetired = Math.max(...months.map(m => m.retired), 1);

    const rows: { label: string; color: string; values: number[]; max: number }[] = [
        { label: 'Created', color: CHART_SERIES[0], values: months.map(m => m.created), max: maxCreated },
        { label: 'Retired', color: CHART_SERIES[1], values: months.map(m => m.retired), max: maxRetired },
    ];

    return (
        <div className="overflow-x-auto">
            <table className="w-full border-collapse">
                <thead>
                    <tr>
                        <th className="text-[9px] text-text-sub font-medium text-left pr-2 w-16" />
                        {months.map(m => (
                            <th key={m.month} className="text-[9px] text-text-sub font-medium text-center px-0.5 pb-1">
                                {formatMonth(m.month)}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map(row => (
                        <tr key={row.label}>
                            <td className="text-[10px] font-medium text-text-main pr-2 py-0.5 whitespace-nowrap">
                                {row.label}
                            </td>
                            {row.values.map((val, i) => (
                                <td key={months[i].month} className="px-0.5 py-0.5">
                                    <div
                                        className="rounded text-center text-[10px] font-medium py-2 min-w-[36px] transition-colors"
                                        style={{
                                            backgroundColor: val > 0
                                                ? `${row.color}${Math.round(intensity(val, row.max) * 200 + 30).toString(16).padStart(2, '0')}`
                                                : '#f4f3ee',
                                            color: intensity(val, row.max) > 0.5 ? '#fff' : '#5a5d5c',
                                        }}
                                        title={`${row.label}: ${val.toLocaleString()} controls in ${formatMonth(months[i].month)}`}
                                    >
                                        {val > 0 ? val.toLocaleString() : '-'}
                                    </div>
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default LifecycleHeatmap;
