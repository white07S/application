import { appConfig } from '../../config/appConfig';

const Home = () => {
    return (
        <main className="pt-12 min-h-screen">
            <section className="relative border-b border-border-light bg-surface-light overflow-hidden">
                <div className="absolute inset-0 bg-grid opacity-60 pointer-events-none"></div>
                <div className="max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4 py-12 grid grid-cols-1 lg:grid-cols-12 gap-4 items-center relative z-10">
                    <div className="lg:col-span-5 flex flex-col gap-6">
                        <div className="inline-flex items-center gap-2 px-2 py-1 bg-white border border-border-light rounded-sm w-fit shadow-sm">
                            <span className="flex h-2 w-2 relative">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                            </span>
                            <span className="text-xs font-mono text-text-sub uppercase tracking-wider">{appConfig.appVersion}</span>
                        </div>
                        <div>
                            <h1 className="text-fluid-hero font-bold tracking-tight text-text-main leading-tight mb-3">
                                Reason over risk. <br />
                                <span className="text-primary">Visualize the unseen.</span>
                            </h1>
                            <p className="text-sm text-text-sub leading-relaxed max-w-md">
                                NFR Connect unifies agentic reasoning with dynamic graph visualization, enabling risk managers to interrogate complex non-financial data relationships in real-time.
                            </p>
                        </div>
                        <div className="flex items-center gap-3 pt-2">
                            <button className="bg-primary hover:bg-[#cc0000] text-white px-5 py-2 text-xs font-semibold rounded shadow-sm transition-all flex items-center gap-2">
                                <span className="material-symbols-outlined text-xl">chat</span>
                                Launch Chat
                            </button>
                            <button className="bg-white border border-border-light hover:bg-surface-light text-text-main px-5 py-2 text-xs font-medium rounded shadow-sm transition-all flex items-center gap-2">
                                <span className="material-symbols-outlined text-xl">play_circle</span>
                                View Demo
                            </button>
                        </div>
                        <div className="flex items-center gap-6 mt-4 border-t border-border-light/60 pt-6">
                            <div>
                                <div className="text-3xl font-mono font-medium text-text-main">{appConfig.stats.riskEntities}</div>
                                <div className="text-xs text-text-sub uppercase tracking-wide">Risk Entities Connected</div>
                            </div>
                            <div>
                                <div className="text-3xl font-mono font-medium text-text-main">{appConfig.stats.activeAgents}</div>
                                <div className="text-xs text-text-sub uppercase tracking-wide">Active LLM Agents</div>
                            </div>
                            <div>
                                <div className="text-3xl font-mono font-medium text-text-main">{appConfig.stats.nodesMapped}</div>
                                <div className="text-xs text-text-sub uppercase tracking-wide">Nodes Mapped</div>
                            </div>
                        </div>
                    </div>
                    <div className="lg:col-span-7">
                        <div className="bg-white rounded-lg border border-border-light shadow-floating overflow-hidden flex flex-col h-[480px]">
                            <div className="bg-surface-light border-b border-border-light px-3 py-2 flex items-center justify-between shrink-0">
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-text-sub text-lg">smart_toy</span>
                                    <span className="text-xs font-medium text-text-main">Agentic Chat Session #8821</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-border-light"></span>
                                    <span className="w-2 h-2 rounded-full bg-border-light"></span>
                                </div>
                            </div>
                            <div className="flex flex-1 overflow-hidden">
                                <div className="w-[40%] border-r border-border-light flex flex-col bg-surface-light">
                                    <div className="flex-1 p-4 overflow-y-auto space-y-5">
                                        <div className="flex flex-col items-end gap-1">
                                            <div className="bg-white border border-border-light p-3 rounded-2xl rounded-tr-sm shadow-sm max-w-[95%]">
                                                <p className="text-sm text-text-main leading-relaxed">Show me open <span className="font-semibold text-primary">Issues</span> impacting <span className="font-semibold text-lagoon">Controls</span> in the Cyber Security domain.</p>
                                            </div>
                                            <div className="flex items-center gap-1.5 mr-1">
                                                <span className="text-xs font-mono text-text-sub">10:42 AM</span>
                                                <div className="w-4 h-4 rounded-full bg-primary text-white flex items-center justify-center text-xs font-bold">JD</div>
                                            </div>
                                        </div>
                                        <div className="flex flex-col gap-1">
                                            <div className="flex items-center gap-2 ml-1">
                                                <div className="w-5 h-5 rounded-full bg-text-main text-white flex items-center justify-center shadow-sm">
                                                    <span className="material-symbols-outlined text-base">smart_toy</span>
                                                </div>
                                                <span className="text-xs font-medium text-text-main">NFR Agent</span>
                                            </div>
                                            <div className="bg-white border border-border-light rounded-lg shadow-sm p-3 w-full">
                                                <div className="border-b border-border-light pb-2 mb-2 space-y-1.5">
                                                    <div className="flex items-center gap-2">
                                                        <span className="relative flex h-2 w-2">
                                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-lagoon opacity-75"></span>
                                                            <span className="relative inline-flex rounded-full h-2 w-2 bg-lagoon"></span>
                                                        </span>
                                                        <span className="text-xs font-mono font-medium text-lagoon uppercase">Thinking Process</span>
                                                    </div>
                                                    <div className="pl-4 space-y-1">
                                                        <div className="flex items-center gap-2 text-xs text-text-sub">
                                                            <span className="material-symbols-outlined text-base text-green-600">check_circle</span>
                                                            <span>Querying Issues → Controls graph</span>
                                                        </div>
                                                        <div className="flex items-center gap-2 text-xs text-text-sub">
                                                            <span className="material-symbols-outlined text-base text-green-600">check_circle</span>
                                                            <span>Filtering by Risk Theme: 1.2 Cyber</span>
                                                        </div>
                                                        <div className="flex items-center gap-2 text-xs text-text-main font-medium">
                                                            <span className="animate-spin h-2.5 w-2.5 border-2 border-primary border-t-transparent rounded-full"></span>
                                                            <span>Mapping remediation actions...</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                <p className="text-sm text-text-main leading-relaxed">
                                                    Found <span className="font-mono text-primary bg-primary/5 px-1 rounded border border-primary/10">ISSUE-2024-03821</span> (Audit finding) impacting <span className="font-mono text-lagoon bg-lagoon/5 px-1 rounded border border-lagoon/10">CTRL-0089124521</span>. Action <span className="font-mono bg-surface-light border border-border-light px-1 rounded">ACTION-2024-00142</span> is in progress.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="p-3 bg-white border-t border-border-light">
                                        <div className="relative">
                                            <input className="w-full text-sm bg-surface-light border border-border-light rounded pl-3 pr-9 py-2.5 focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-text-sub/60" placeholder="Ask a follow-up regarding the risk owner..." type="text" />
                                            <button className="absolute right-1.5 top-1.5 p-1 text-text-sub hover:text-primary transition-colors">
                                                <span className="material-symbols-outlined text-xl">arrow_upward</span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                <div className="w-[60%] bg-surface-light relative overflow-hidden flex items-center justify-center">
                                    <div className="absolute inset-0 bg-[radial-gradient(#d1d5db_1px,transparent_1px)] [background-size:20px_20px] opacity-50"></div>
                                    <svg className="absolute inset-0 w-full h-full pointer-events-none">
                                        <defs>
                                            <marker id="arrow-red" markerHeight="10" markerUnits="strokeWidth" markerWidth="10" orient="auto" refX="9" refY="3">
                                                <path d="M0,0 L0,6 L9,3 z" fill="#e60000"></path>
                                            </marker>
                                            <marker id="arrow-teal" markerHeight="10" markerUnits="strokeWidth" markerWidth="10" orient="auto" refX="9" refY="3">
                                                <path d="M0,0 L0,6 L9,3 z" fill="#008e97"></path>
                                            </marker>
                                            <marker id="arrow-blue" markerHeight="10" markerUnits="strokeWidth" markerWidth="10" orient="auto" refX="9" refY="3">
                                                <path d="M0,0 L0,6 L9,3 z" fill="#3b82f6"></path>
                                            </marker>
                                            <marker id="arrow-purple" markerHeight="10" markerUnits="strokeWidth" markerWidth="10" orient="auto" refX="9" refY="3">
                                                <path d="M0,0 L0,6 L9,3 z" fill="#8b5cf6"></path>
                                            </marker>
                                        </defs>
                                        {/* Issue → Control: IMPACTS_CONTROL */}
                                        <line markerEnd="url(#arrow-teal)" stroke="#008e97" strokeWidth="1.5" x1="42%" x2="72%" y1="45%" y2="28%"></line>
                                        <text dy="-5" fill="#008e97" fontFamily="monospace" fontSize="8" textAnchor="middle" x="57%" y="36%">IMPACTS_CONTROL</text>
                                        {/* Action → Issue: REMEDIATES */}
                                        <line markerEnd="url(#arrow-red)" stroke="#e60000" strokeWidth="1.5" x1="25%" x2="38%" y1="72%" y2="52%"></line>
                                        <text dy="12" fill="#e60000" fontFamily="monospace" fontSize="8" textAnchor="middle" x="30%" y="62%">REMEDIATES</text>
                                        {/* Control → Risk Theme: HAS_RISK_THEME */}
                                        <line markerEnd="url(#arrow-purple)" stroke="#8b5cf6" strokeDasharray="3 2" strokeWidth="1.5" x1="78%" x2="78%" y1="35%" y2="68%"></line>
                                        <text fill="#8b5cf6" fontFamily="monospace" fontSize="8" textAnchor="start" x="80%" y="52%">HAS_RISK</text>
                                        <text fill="#8b5cf6" fontFamily="monospace" fontSize="8" textAnchor="start" x="80%" y="60%">_THEME</text>
                                        {/* Issue → Risk Theme: CLASSIFIED_AS */}
                                        <line markerEnd="url(#arrow-purple)" stroke="#8b5cf6" strokeDasharray="3 2" strokeWidth="1.5" x1="48%" x2="68%" y1="52%" y2="75%"></line>
                                        <text dy="-5" fill="#8b5cf6" fontFamily="monospace" fontSize="8" textAnchor="middle" x="58%" y="68%">CLASSIFIED_AS</text>
                                    </svg>
                                    {/* Issue Node (Central) */}
                                    <div className="absolute top-[45%] left-[42%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10 group cursor-pointer">
                                        <div className="bg-red-50 border-2 border-primary text-primary px-3 py-1.5 rounded shadow-lg flex items-center gap-2 ring-4 ring-red-500/10 transition-all group-hover:ring-red-500/20">
                                            <span className="material-symbols-outlined text-xl">bug_report</span>
                                            <span className="text-xs font-bold font-mono">ISSUE-2024-03821</span>
                                        </div>
                                        <span className="mt-1 text-xs font-medium text-text-sub bg-white/90 px-1.5 py-0.5 rounded backdrop-blur border border-border-light shadow-sm">Audit Finding: DLP Gap</span>
                                    </div>
                                    {/* Control Node */}
                                    <div className="absolute top-[22%] left-[78%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10">
                                        <div className="bg-teal-50 border-2 border-lagoon text-lagoon px-3 py-1.5 rounded shadow-md flex items-center gap-2">
                                            <span className="material-symbols-outlined text-xl">gpp_good</span>
                                            <span className="text-xs font-bold font-mono">CTRL-0089124521</span>
                                        </div>
                                        <span className="mt-1 text-xs font-medium text-text-sub bg-white/90 px-1.5 py-0.5 rounded backdrop-blur border border-border-light shadow-sm">DLP Gateway Control</span>
                                    </div>
                                    {/* Action Node */}
                                    <div className="absolute top-[75%] left-[22%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10">
                                        <div className="bg-blue-50 border-2 border-blue-500 text-blue-600 px-3 py-1.5 rounded shadow-md flex items-center gap-2">
                                            <span className="material-symbols-outlined text-xl">task_alt</span>
                                            <span className="text-xs font-bold font-mono">ACTION-2024-00142</span>
                                        </div>
                                        <div className="mt-1 flex items-center gap-1">
                                            <span className="text-xs font-medium text-white bg-amber-500 px-1.5 py-0.5 rounded shadow-sm">In Progress</span>
                                        </div>
                                    </div>
                                    {/* Risk Theme Node */}
                                    <div className="absolute top-[78%] left-[75%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10">
                                        <div className="bg-purple-50 border border-purple-400 text-purple-600 px-2.5 py-1.5 rounded shadow-sm flex items-center gap-2">
                                            <span className="material-symbols-outlined text-lg">label</span>
                                            <span className="text-xs font-bold font-mono">1.2 Cyber Security</span>
                                        </div>
                                        <span className="mt-1 text-xs font-medium text-text-sub bg-white/90 px-1.5 py-0.5 rounded backdrop-blur border border-border-light shadow-sm">NFR Risk Theme</span>
                                    </div>
                                    {/* Legend */}
                                    <div className="absolute bottom-3 right-3 bg-white/95 backdrop-blur border border-border-light p-2 rounded shadow-sm flex flex-col gap-1 z-20">
                                        <div className="flex items-center gap-2">
                                            <span className="w-3 h-3 rounded bg-red-50 border border-primary"></span>
                                            <span className="text-xs text-text-sub font-mono">Issue</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="w-3 h-3 rounded bg-teal-50 border border-lagoon"></span>
                                            <span className="text-xs text-text-sub font-mono">Control</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="w-3 h-3 rounded bg-blue-50 border border-blue-500"></span>
                                            <span className="text-xs text-text-sub font-mono">Action</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="w-3 h-3 rounded bg-purple-50 border border-purple-400"></span>
                                            <span className="text-xs text-text-sub font-mono">Risk Theme</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
            <section className="py-10 bg-surface-light border-b border-border-light">
                <div className="max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-fluid-xl font-bold text-text-main uppercase tracking-tight">Data Tracked by NFR Connect</h2>
                        <div className="flex items-center gap-2 text-xs text-text-sub font-mono bg-white px-2 py-1 border border-border-light rounded-sm">
                            LAST_SYNC: {appConfig.meta.lastSync}
                        </div>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-5 2xl:grid-cols-5 gap-3">
                        <div className="bg-white p-3 rounded border border-border-light shadow-card hover:shadow-md transition-shadow group">
                            <div className="flex items-center gap-2 mb-3 text-text-sub group-hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-2xl">bug_report</span>
                                <span className="text-xs font-medium">Issues</span>
                            </div>
                            <div className="text-2xl font-mono font-medium text-text-main mb-1 tracking-tight">{appConfig.stats.issues.count}</div>
                            <div className="flex items-center gap-1 text-xs font-mono text-green-600 bg-green-50 w-fit px-1.5 py-0.5 rounded">
                                <span className="material-symbols-outlined text-base">arrow_upward</span>
                                <span>+{appConfig.stats.issues.ingested} Ingested</span>
                            </div>
                        </div>
                        <div className="bg-white p-3 rounded border border-border-light shadow-card hover:shadow-md transition-shadow group">
                            <div className="flex items-center gap-2 mb-3 text-text-sub group-hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-2xl">gpp_good</span>
                                <span className="text-xs font-medium">Controls</span>
                            </div>
                            <div className="text-2xl font-mono font-medium text-text-main mb-1 tracking-tight">{appConfig.stats.controls.count}</div>
                            <div className="flex items-center gap-1 text-xs font-mono text-green-600 bg-green-50 w-fit px-1.5 py-0.5 rounded">
                                <span className="material-symbols-outlined text-base">arrow_upward</span>
                                <span>+{appConfig.stats.controls.ingested} Ingested</span>
                            </div>
                        </div>
                        <div className="bg-white p-3 rounded border border-border-light shadow-card hover:shadow-md transition-shadow group">
                            <div className="flex items-center gap-2 mb-3 text-text-sub group-hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-2xl">notifications_active</span>
                                <span className="text-xs font-medium">Events</span>
                            </div>
                            <div className="text-2xl font-mono font-medium text-text-main mb-1 tracking-tight">{appConfig.stats.events.count}</div>
                            <div className="flex items-center gap-1 text-xs font-mono text-green-600 bg-green-50 w-fit px-1.5 py-0.5 rounded">
                                <span className="material-symbols-outlined text-base">arrow_upward</span>
                                <span>+{appConfig.stats.events.ingested} Ingested</span>
                            </div>
                        </div>
                        <div className="bg-white p-3 rounded border border-border-light shadow-card hover:shadow-md transition-shadow group">
                            <div className="flex items-center gap-2 mb-3 text-text-sub group-hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-2xl">trending_down</span>
                                <span className="text-xs font-medium">External Loss</span>
                            </div>
                            <div className="text-2xl font-mono font-medium text-text-main mb-1 tracking-tight">{appConfig.stats.externalLoss.count}</div>
                            <div className="flex items-center gap-1 text-xs font-mono text-green-600 bg-green-50 w-fit px-1.5 py-0.5 rounded">
                                <span className="material-symbols-outlined text-base">arrow_upward</span>
                                <span>+{appConfig.stats.externalLoss.ingested} Ingested</span>
                            </div>
                        </div>
                        <div className="bg-white p-3 rounded border border-border-light shadow-card hover:shadow-md transition-shadow group">
                            <div className="flex items-center gap-2 mb-3 text-text-sub group-hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-2xl">policy</span>
                                <span className="text-xs font-medium">Policies</span>
                            </div>
                            <div className="text-2xl font-mono font-medium text-text-main mb-1 tracking-tight">{appConfig.stats.policies.count}</div>
                            <div className="flex items-center gap-1 text-xs font-mono text-green-600 bg-green-50 w-fit px-1.5 py-0.5 rounded">
                                <span className="material-symbols-outlined text-base">arrow_upward</span>
                                <span>+{appConfig.stats.policies.ingested} Ingested</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
            <section className="py-16 bg-white border-b border-border-light overflow-hidden">
                <div className="max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4">
                    <div className="mb-10 max-w-2xl">
                        <h2 className="text-fluid-2xl font-bold text-text-main tracking-tight mb-3">
                            Platform Capabilities
                        </h2>
                        <p className="text-text-sub text-sm leading-relaxed">
                            Advanced features powering the next generation of non-financial risk management.
                        </p>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                        {appConfig.features.map((feature, idx) => (
                            <div
                                key={idx}
                                className={`${feature.colSpan} relative rounded-sm bg-surface-light border border-border-light p-4 overflow-hidden group transition-all h-[180px] flex flex-col justify-between hover:bg-white hover:shadow-md`}
                            >
                                <div className="absolute inset-0 bg-grid opacity-30 pointer-events-none"></div>
                                <div className={`absolute -right-10 -bottom-10 w-40 h-40 ${feature.color} opacity-10 blur-3xl rounded-full group-hover:opacity-20 transition-opacity`}></div>

                                <div className="relative z-10 translate-z-[20px]">
                                    <div className={`w-12 h-12 rounded-lg ${feature.color} bg-opacity-10 flex items-center justify-center mb-4`}>
                                        <span className={`material-symbols-outlined text-2xl ${feature.color.replace('bg-', 'text-')}`}>
                                            {feature.icon}
                                        </span>
                                    </div>
                                    <h3 className="text-fluid-xl font-bold text-text-main mb-2 group-hover:text-primary transition-colors">
                                        {feature.title}
                                    </h3>
                                    <p className="text-text-sub text-sm leading-relaxed max-w-[90%]">
                                        {feature.desc}
                                    </p>
                                </div>

                                <div className="relative z-10 flex items-center gap-2 text-xs font-semibold text-primary opacity-0 translate-y-4 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-300">
                                    <span>Learn more</span>
                                    <span className="material-symbols-outlined text-xl">arrow_forward</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
            <section className="py-10 bg-white border-b border-border-light">
                <div className="max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4">
                    {/* Risk Models Panel */}
                    <div className="flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-xl font-bold text-text-main uppercase tracking-tight">Models Portfolio</h2>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                            {Object.values(appConfig.models).map((model) => (
                                <div key={model.id} className="bg-surface-light border border-border-light rounded-lg p-4 hover:bg-white hover:shadow-md transition-all group flex flex-col gap-3">
                                    <div className="flex items-start justify-between">
                                        <div className="p-2 bg-white border border-border-light rounded shadow-sm shrink-0">
                                            <span className="material-symbols-outlined text-primary text-xl">
                                                {model.id.includes('DICE') ? 'bubble_chart' : model.id.includes('HALO') ? 'account_tree' : 'psychology_alt'}
                                            </span>
                                        </div>
                                        <span className={`px-2 py-0.5 rounded text-xs font-bold font-mono ${model.statusColor.bg} ${model.statusColor.text} border ${model.statusColor.border} uppercase shrink-0`}>
                                            {model.status}
                                        </span>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className="text-base font-bold text-text-main">{model.name}</h3>
                                            <span className="text-xs font-mono text-text-sub opacity-60">{model.id}</span>
                                        </div>
                                        <p className="text-sm text-text-sub leading-relaxed line-clamp-2 mb-3">{model.desc}</p>
                                        <div className="flex items-center justify-between">
                                            <a href="#" className="text-xs font-medium text-text-sub hover:text-primary flex items-center gap-1 transition-colors">
                                                <span className="material-symbols-outlined text-base">description</span>
                                                Documentation
                                            </a>
                                            <a href="#" className="text-xs font-medium text-primary hover:underline flex items-center gap-0.5">
                                                {model.id.includes('AGNT') ? 'Roadmap' : model.id.includes('HALO') ? 'Details' : 'Docs'}
                                                <span className="material-symbols-outlined text-sm">arrow_forward</span>
                                            </a>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </section>
        </main>
    );
};

export default Home;
