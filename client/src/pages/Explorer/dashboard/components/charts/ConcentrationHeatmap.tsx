import React from 'react';
import type { ConcentrationData } from '../../types';
import { CHART_SERIES } from '../../chartColors';

interface ConcentrationHeatmapProps {
    data: ConcentrationData;
    color?: string;
}

const intensity = (value: number, max: number): number => {
    if (max === 0 || value === 0) return 0;
    return Math.max(0.1, value / max);
};

const formatMonth = (month: string): string => {
    const [y, m] = month.split('-');
    const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${names[parseInt(m, 10) - 1]} ${y.slice(2)}`;
};

const ConcentrationHeatmap: React.FC<ConcentrationHeatmapProps> = ({
    data,
    color = CHART_SERIES[0],
}) => {
    const monthLabels = data.months.map(m => m.month);

    // Max cell value for heatmap intensity
    let maxVal = 1;
    for (const valMap of Object.values(data.grid)) {
        for (const cnt of Object.values(valMap)) {
            if (cnt > maxVal) maxVal = cnt;
        }
    }

    // Others max
    const othersMax = Math.max(...data.months.map(m => m.others_count), 1);

    // Row totals for the proportional bar column
    const rowTotals: Record<string, number> = {};
    for (const val of data.top_values) {
        rowTotals[val] = Object.values(data.grid[val] ?? {}).reduce((a, b) => a + b, 0);
    }
    const othersTotal = data.months.reduce((a, m) => a + m.others_count, 0);
    const maxRowTotal = Math.max(...Object.values(rowTotals), othersTotal, 1);

    // Column (month) totals for the bottom summary row
    const colTotals: Record<string, number> = {};
    for (const mo of monthLabels) {
        let sum = 0;
        for (const val of data.top_values) {
            sum += data.grid[val]?.[mo] ?? 0;
        }
        sum += data.months.find(m => m.month === mo)?.others_count ?? 0;
        colTotals[mo] = sum;
    }
    const maxColTotal = Math.max(...Object.values(colTotals), 1);

    return (
        <div className="overflow-x-auto">
            <table className="w-full border-collapse">
                <thead>
                    <tr>
                        <th className="text-[9px] text-text-sub font-medium text-left pr-2 w-32 min-w-[120px]" />
                        {monthLabels.map(mo => (
                            <th key={mo} className="text-[9px] text-text-sub font-medium text-center px-0.5 pb-1">
                                {formatMonth(mo)}
                            </th>
                        ))}
                        <th className="text-[9px] text-text-sub font-medium text-right pl-2 pr-1 pb-1 w-20">
                            Total
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {data.top_values.map(val => {
                        const total = rowTotals[val] ?? 0;
                        return (
                            <tr key={val}>
                                <td
                                    className="text-[10px] font-medium text-text-main pr-2 py-0.5 whitespace-nowrap overflow-hidden text-ellipsis max-w-[120px]"
                                    title={val}
                                >
                                    {val}
                                </td>
                                {monthLabels.map(mo => {
                                    const cnt = data.grid[val]?.[mo] ?? 0;
                                    return (
                                        <td key={mo} className="px-0.5 py-0.5">
                                            <div
                                                className="rounded text-center text-[10px] font-medium py-1.5 min-w-[36px] transition-colors"
                                                style={{
                                                    backgroundColor: cnt > 0
                                                        ? `${color}${Math.round(intensity(cnt, maxVal) * 200 + 30).toString(16).padStart(2, '0')}`
                                                        : '#f4f3ee',
                                                    color: intensity(cnt, maxVal) > 0.5 ? '#fff' : '#5a5d5c',
                                                }}
                                                title={`${val}: ${cnt.toLocaleString()} controls in ${formatMonth(mo)}`}
                                            >
                                                {cnt > 0 ? cnt.toLocaleString() : '-'}
                                            </div>
                                        </td>
                                    );
                                })}
                                {/* Proportional bar + total */}
                                <td className="pl-2 pr-1 py-0.5">
                                    <div className="relative h-6 flex items-center">
                                        <div
                                            className="absolute inset-y-0 left-0 rounded"
                                            style={{
                                                width: `${Math.max(4, (total / maxRowTotal) * 100)}%`,
                                                backgroundColor: `${color}25`,
                                            }}
                                        />
                                        <span className="relative text-[10px] font-semibold text-text-main pl-1.5">
                                            {total.toLocaleString()}
                                        </span>
                                    </div>
                                </td>
                            </tr>
                        );
                    })}
                    {/* Others row */}
                    <tr className="border-t border-border-light">
                        <td className="text-[10px] font-medium text-text-sub pr-2 py-0.5 italic">
                            Others
                        </td>
                        {data.months.map(mp => (
                            <td key={mp.month} className="px-0.5 py-0.5">
                                <div
                                    className="rounded text-center text-[10px] font-medium py-1.5 min-w-[36px] transition-colors"
                                    style={{
                                        backgroundColor: mp.others_count > 0
                                            ? `#94a3b8${Math.round(intensity(mp.others_count, othersMax) * 200 + 30).toString(16).padStart(2, '0')}`
                                            : '#f4f3ee',
                                        color: intensity(mp.others_count, othersMax) > 0.5 ? '#fff' : '#5a5d5c',
                                    }}
                                    title={`Others: ${mp.others_count.toLocaleString()} controls in ${formatMonth(mp.month)}`}
                                >
                                    {mp.others_count > 0 ? mp.others_count.toLocaleString() : '-'}
                                </div>
                            </td>
                        ))}
                        <td className="pl-2 pr-1 py-0.5">
                            <div className="relative h-6 flex items-center">
                                <div
                                    className="absolute inset-y-0 left-0 rounded"
                                    style={{
                                        width: `${Math.max(4, (othersTotal / maxRowTotal) * 100)}%`,
                                        backgroundColor: '#94a3b825',
                                    }}
                                />
                                <span className="relative text-[10px] font-semibold text-text-sub pl-1.5 italic">
                                    {othersTotal.toLocaleString()}
                                </span>
                            </div>
                        </td>
                    </tr>
                    {/* Month totals row */}
                    <tr className="border-t-2 border-border-light">
                        <td className="text-[10px] font-semibold text-text-main pr-2 py-1">
                            Total
                        </td>
                        {monthLabels.map(mo => {
                            const t = colTotals[mo] ?? 0;
                            return (
                                <td key={mo} className="px-0.5 py-1">
                                    <div
                                        className="rounded text-center text-[10px] font-semibold py-1.5 min-w-[36px]"
                                        style={{
                                            backgroundColor: t > 0
                                                ? `${color}${Math.round(intensity(t, maxColTotal) * 140 + 20).toString(16).padStart(2, '0')}`
                                                : '#f4f3ee',
                                            color: intensity(t, maxColTotal) > 0.6 ? '#fff' : '#5a5d5c',
                                        }}
                                        title={`Total: ${t.toLocaleString()} controls in ${formatMonth(mo)}`}
                                    >
                                        {t > 0 ? t.toLocaleString() : '-'}
                                    </div>
                                </td>
                            );
                        })}
                        <td className="pl-2 pr-1 py-1">
                            <span className="text-[10px] font-semibold text-text-main">
                                {(Object.values(colTotals).reduce((a, b) => a + b, 0)).toLocaleString()}
                            </span>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    );
};

export default ConcentrationHeatmap;
