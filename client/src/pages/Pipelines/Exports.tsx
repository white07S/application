import type { FC } from 'react';
import { useState, useEffect, useCallback } from 'react';
import PipelinesSidebar from './components/PipelinesSidebar';
import { useAuth } from '../../auth/useAuth';
import { appConfig } from '../../config/appConfig';

interface TemplateInfo {
    name: string;
    description: string;
}

const formatTemplateName = (name: string): string =>
    name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

const Exports: FC = () => {
    const { getApiAccessToken } = useAuth();
    const [templates, setTemplates] = useState<TemplateInfo[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedTemplate, setSelectedTemplate] = useState<string>('');
    const [evaluationDate, setEvaluationDate] = useState<string>('');
    const [exporting, setExporting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const fetchTemplates = useCallback(async () => {
        try {
            const token = await getApiAccessToken();
            if (!token) {
                setError('Authentication failed. Please sign in again.');
                return;
            }

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/export/templates`, {
                headers: { 'X-MS-TOKEN-AAD': token },
            });

            if (response.ok) {
                const data = await response.json();
                setTemplates(data.templates);
                if (data.templates.length > 0 && !selectedTemplate) {
                    setSelectedTemplate(data.templates[0].name);
                }
            } else if (response.status === 403) {
                setError('You do not have permission to access exports.');
            } else {
                setError('Failed to load export templates. Please try again.');
            }
        } catch (err) {
            console.error('Failed to fetch templates:', err);
            setError('Unable to reach the server. Check your network connection.');
        } finally {
            setLoading(false);
        }
    }, [getApiAccessToken, selectedTemplate]);

    useEffect(() => {
        fetchTemplates();
    }, [fetchTemplates]);

    const handleExport = async () => {
        if (!selectedTemplate || !evaluationDate) return;

        // Validate date is not in the future (string compare avoids timezone issues)
        if (evaluationDate > todayStr) {
            setError('Evaluation date cannot be in the future.');
            return;
        }

        setExporting(true);
        setError(null);
        setSuccess(null);

        try {
            const token = await getApiAccessToken();
            if (!token) {
                setError('Authentication failed. Please sign in again.');
                return;
            }

            const response = await fetch(`${appConfig.api.baseUrl}/api/v2/export/run`, {
                method: 'POST',
                headers: {
                    'X-MS-TOKEN-AAD': token,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    template_name: selectedTemplate,
                    evaluation_date: evaluationDate,
                }),
            });

            if (response.ok) {
                const blob = await response.blob();
                const contentDisposition = response.headers.get('content-disposition');
                let filename = `${selectedTemplate}_${evaluationDate.replace(/-/g, '')}.xlsx`;
                if (contentDisposition) {
                    const match = contentDisposition.match(/filename="?(.+?)"?$/);
                    if (match) filename = match[1];
                }

                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                setSuccess(`Export downloaded: ${filename}`);
            } else {
                // Handle both JSON and non-JSON error responses
                let message = `Export failed (HTTP ${response.status})`;
                try {
                    const data = await response.json();
                    if (data.detail) message = data.detail;
                } catch {
                    // Response wasn't JSON — use status text
                    message = `Export failed: ${response.statusText || 'Server error'} (HTTP ${response.status})`;
                }
                setError(message);
            }
        } catch (err) {
            console.error('Export failed:', err);
            setError('Export failed. Unable to reach the server — check your network connection.');
        } finally {
            setExporting(false);
        }
    };

    const selectedInfo = templates.find(t => t.name === selectedTemplate);
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

    return (
        <main className="min-h-screen">
            <div className="w-full max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4">
                <div className="flex">
                    {/* Sidebar */}
                    <div className="sticky top-12 h-[calc(100vh-48px)] overflow-y-auto py-4">
                        <PipelinesSidebar />
                    </div>

                    {/* Main Content */}
                    <div className="flex-1 min-w-0 py-4 pl-4 flex flex-col gap-4">
                        {/* Page Header */}
                        <div>
                            <h1 className="text-xl font-bold text-text-main flex items-center gap-2">
                                <span className="material-symbols-outlined text-primary">output</span>
                                Template Exports
                            </h1>
                            <p className="text-xs text-text-sub mt-1">
                                Generate and download enrichment reports as Excel files
                            </p>
                        </div>

                        {/* Export Form */}
                        <div className="bg-white border border-border-light rounded shadow-card">
                            <div className="px-5 py-3 border-b border-border-light bg-surface-light/50">
                                <h2 className="text-xs font-bold text-text-main uppercase tracking-wide flex items-center gap-2">
                                    <span className="material-symbols-outlined text-text-sub text-[16px]">settings</span>
                                    Export Configuration
                                </h2>
                            </div>

                            {loading ? (
                                <div className="p-8 text-center">
                                    <span className="material-symbols-outlined animate-spin text-2xl text-text-sub">refresh</span>
                                    <p className="text-xs text-text-sub mt-2">Loading templates...</p>
                                </div>
                            ) : templates.length === 0 ? (
                                <div className="p-8 text-center">
                                    <span className="material-symbols-outlined text-3xl text-border-dark">inbox</span>
                                    <p className="text-xs text-text-sub mt-2">No export templates available</p>
                                </div>
                            ) : (
                                <div className="p-5 flex flex-col gap-5">
                                    {/* Template Selector */}
                                    <div>
                                        <label className="block text-xs font-medium text-text-main mb-1.5">
                                            Template
                                        </label>
                                        <select
                                            value={selectedTemplate}
                                            onChange={e => setSelectedTemplate(e.target.value)}
                                            disabled={exporting}
                                            className="w-full max-w-md px-3 py-2 text-sm border border-border-light rounded bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary disabled:opacity-50"
                                        >
                                            {templates.map(t => (
                                                <option key={t.name} value={t.name}>
                                                    {formatTemplateName(t.name)}
                                                </option>
                                            ))}
                                        </select>
                                        {selectedInfo && (
                                            <p className="text-[11px] text-text-sub mt-1.5">{selectedInfo.description}</p>
                                        )}
                                    </div>

                                    {/* Evaluation Date */}
                                    <div>
                                        <label className="block text-xs font-medium text-text-main mb-1.5">
                                            Evaluation Date
                                        </label>
                                        <input
                                            type="date"
                                            value={evaluationDate}
                                            max={todayStr}
                                            onChange={e => { setEvaluationDate(e.target.value); setError(null); }}
                                            disabled={exporting}
                                            className="w-full max-w-md px-3 py-2 text-sm border border-border-light rounded bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary disabled:opacity-50"
                                        />
                                        <p className="text-[11px] text-text-sub mt-1.5">
                                            The as-of date for the report. Use a date after a completed ingestion.
                                        </p>
                                    </div>

                                    {/* Export Button */}
                                    <div className="pt-2">
                                        <button
                                            onClick={handleExport}
                                            disabled={!selectedTemplate || !evaluationDate || exporting}
                                            className={`flex items-center gap-2 px-5 py-2 text-xs font-medium rounded transition-colors ${
                                                selectedTemplate && evaluationDate && !exporting
                                                    ? 'bg-primary hover:bg-primary-dark text-white'
                                                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                            }`}
                                        >
                                            {exporting ? (
                                                <>
                                                    <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>
                                                    Generating...
                                                </>
                                            ) : (
                                                <>
                                                    <span className="material-symbols-outlined text-[16px]">download</span>
                                                    Export & Download
                                                </>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Success Message */}
                        {success && (
                            <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2">
                                <span className="material-symbols-outlined text-green-600">check_circle</span>
                                <p className="text-xs text-green-800 font-medium flex-1">{success}</p>
                                <button onClick={() => setSuccess(null)} className="text-green-400 hover:text-green-600">
                                    <span className="material-symbols-outlined text-[16px]">close</span>
                                </button>
                            </div>
                        )}

                        {/* Error Message */}
                        {error && (
                            <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
                                <span className="material-symbols-outlined text-red-600">error</span>
                                <p className="text-xs text-red-800 font-medium flex-1">{error}</p>
                                <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
                                    <span className="material-symbols-outlined text-[16px]">close</span>
                                </button>
                            </div>
                        )}

                        {/* Info Banner */}
                        <div className="bg-blue-50 border border-blue-100 rounded p-3">
                            <div className="flex items-start gap-2">
                                <span className="material-symbols-outlined text-blue-600">info</span>
                                <div className="text-xs text-blue-800">
                                    <p className="font-medium">Template Exports</p>
                                    <p className="mt-1 text-blue-700">
                                        Select a template and evaluation date to generate an Excel report.
                                        The evaluation date determines the point-in-time snapshot of enrichment data.
                                    </p>
                                    <p className="mt-2 text-blue-600 text-[10px]">
                                        Only active key controls with completed enrichment are included in the export.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    );
};

export default Exports;
