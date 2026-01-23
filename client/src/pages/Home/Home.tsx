import React from 'react';
import { appConfig } from '../../config/appConfig';

const Home = () => {
    // Mouse move handler for wobble effect
    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
        const card = e.currentTarget;
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -5; // Max 5deg rotation
        const rotateY = ((x - centerX) / centerX) * 5;

        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
    };

    const handleMouseLeave = (e: React.MouseEvent<HTMLDivElement>) => {
        e.currentTarget.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)';
    };

    return (
        <main className="pt-12 min-h-screen">
            <section className="relative border-b border-border-light bg-surface-light overflow-hidden">
                <div className="absolute inset-0 bg-grid opacity-60 pointer-events-none"></div>
                <div className="max-w-[95%] mx-auto px-6 py-12 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center relative z-10">
                    <div className="lg:col-span-5 flex flex-col gap-6">
                        <div className="inline-flex items-center gap-2 px-2 py-1 bg-white border border-border-light rounded-sm w-fit shadow-sm">
                            <span className="flex h-2 w-2 relative">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                            </span>
                            <span className="text-[10px] font-mono text-text-sub uppercase tracking-wider">{appConfig.appVersion}</span>
                        </div>
                        <div>
                            <h1 className="text-3xl lg:text-[32px] font-bold tracking-tight text-text-main leading-tight mb-3">
                                Reason over risk. <br />
                                <span className="text-primary">Visualize the unseen.</span>
                            </h1>
                            <p className="text-sm text-text-sub leading-relaxed max-w-md">
                                NFR Connect unifies agentic reasoning with dynamic graph visualization, enabling risk managers to interrogate complex non-financial data relationships in real-time.
                            </p>
                        </div>
                        <div className="flex items-center gap-3 pt-2">
                            <button className="bg-primary hover:bg-[#cc0000] text-white px-5 py-2 text-xs font-semibold rounded shadow-sm transition-all flex items-center gap-2">
                                <span className="material-symbols-outlined text-[16px]">chat</span>
                                Launch Chat
                            </button>
                            <button className="bg-white border border-border-light hover:bg-surface-light text-text-main px-5 py-2 text-xs font-medium rounded shadow-sm transition-all flex items-center gap-2">
                                <span className="material-symbols-outlined text-[16px]">play_circle</span>
                                View Demo
                            </button>
                        </div>
                        <div className="flex items-center gap-6 mt-4 border-t border-border-light/60 pt-6">
                            <div>
                                <div className="text-[20px] font-mono font-medium text-text-main">{appConfig.stats.riskEntities}</div>
                                <div className="text-[10px] text-text-sub uppercase tracking-wide">Risk Entities Connected</div>
                            </div>
                            <div>
                                <div className="text-[20px] font-mono font-medium text-text-main">{appConfig.stats.activeAgents}</div>
                                <div className="text-[10px] text-text-sub uppercase tracking-wide">Active LLM Agents</div>
                            </div>
                            <div>
                                <div className="text-[20px] font-mono font-medium text-text-main">{appConfig.stats.nodesMapped}</div>
                                <div className="text-[10px] text-text-sub uppercase tracking-wide">Nodes Mapped</div>
                            </div>
                        </div>
                    </div>
                    <div className="lg:col-span-7">
                        <div className="bg-white rounded-lg border border-border-light shadow-floating overflow-hidden flex flex-col h-[480px]">
                            <div className="bg-surface-light border-b border-border-light px-3 py-2 flex items-center justify-between shrink-0">
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-text-sub text-[14px]">smart_toy</span>
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
                                                <p className="text-[11px] text-text-main leading-relaxed">Show me <span className="font-semibold text-primary">Interconnected Control Failures</span> for Q3 in the APAC region.</p>
                                            </div>
                                            <div className="flex items-center gap-1.5 mr-1">
                                                <span className="text-[9px] font-mono text-text-sub">10:42 AM</span>
                                                <div className="w-4 h-4 rounded-full bg-primary text-white flex items-center justify-center text-[8px] font-bold">JD</div>
                                            </div>
                                        </div>
                                        <div className="flex flex-col gap-1">
                                            <div className="flex items-center gap-2 ml-1">
                                                <div className="w-5 h-5 rounded-full bg-text-main text-white flex items-center justify-center shadow-sm">
                                                    <span className="material-symbols-outlined text-[12px]">smart_toy</span>
                                                </div>
                                                <span className="text-[10px] font-medium text-text-main">NFR Agent</span>
                                            </div>
                                            <div className="bg-white border border-border-light rounded-lg shadow-sm p-3 w-full">
                                                <div className="border-b border-border-light pb-2 mb-2 space-y-1.5">
                                                    <div className="flex items-center gap-2">
                                                        <span className="relative flex h-2 w-2">
                                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-lagoon opacity-75"></span>
                                                            <span className="relative inline-flex rounded-full h-2 w-2 bg-lagoon"></span>
                                                        </span>
                                                        <span className="text-[10px] font-mono font-medium text-lagoon uppercase">Thinking Process</span>
                                                    </div>
                                                    <div className="pl-4 space-y-1">
                                                        <div className="flex items-center gap-2 text-[10px] text-text-sub">
                                                            <span className="material-symbols-outlined text-[12px] text-green-600">check_circle</span>
                                                            <span>Searching Knowledge Graph</span>
                                                        </div>
                                                        <div className="flex items-center gap-2 text-[10px] text-text-sub">
                                                            <span className="material-symbols-outlined text-[12px] text-green-600">check_circle</span>
                                                            <span>Mapping 14 Control Nodes</span>
                                                        </div>
                                                        <div className="flex items-center gap-2 text-[10px] text-text-main font-medium">
                                                            <span className="animate-spin h-2.5 w-2.5 border-2 border-primary border-t-transparent rounded-full"></span>
                                                            <span>Generating Insight...</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                <p className="text-[11px] text-text-main leading-relaxed">
                                                    I've detected a critical cluster. <span className="font-mono text-primary bg-primary/5 px-1 rounded border border-primary/10">Event-402</span> triggered a cascade failure bypassing <span className="font-mono bg-surface-light border border-border-light px-1 rounded">Control-CP99</span>. Visualizing the propagation path now.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="p-3 bg-white border-t border-border-light">
                                        <div className="relative">
                                            <input className="w-full text-[11px] bg-surface-light border border-border-light rounded pl-3 pr-9 py-2.5 focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-text-sub/60" placeholder="Ask a follow-up regarding the risk owner..." type="text" />
                                            <button className="absolute right-1.5 top-1.5 p-1 text-text-sub hover:text-primary transition-colors">
                                                <span className="material-symbols-outlined text-[16px]">arrow_upward</span>
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
                                            <marker id="arrow-gray" markerHeight="10" markerUnits="strokeWidth" markerWidth="10" orient="auto" refX="9" refY="3">
                                                <path d="M0,0 L0,6 L9,3 z" fill="#9ca3af"></path>
                                            </marker>
                                        </defs>
                                        <line markerEnd="url(#arrow-red)" stroke="#e60000" strokeDasharray="4 2" strokeWidth="1.5" x1="50%" x2="75%" y1="50%" y2="30%"></line>
                                        <text dy="-5" fill="#e60000" fontFamily="monospace" fontSize="9" textAnchor="middle" x="62%" y="40%">BYPASSED</text>
                                        <line markerEnd="url(#arrow-teal)" stroke="#008e97" strokeWidth="1.5" x1="75%" x2="25%" y1="30%" y2="20%"></line>
                                        <text dy="-5" fill="#008e97" fontFamily="monospace" fontSize="9" textAnchor="middle" x="50%" y="25%">ENFORCES</text>
                                        <line markerEnd="url(#arrow-gray)" stroke="#9ca3af" strokeWidth="1.5" x1="50%" x2="50%" y1="50%" y2="80%"></line>
                                        <text fill="#6b7280" fontFamily="monospace" fontSize="9" textAnchor="start" x="52%" y="65%">ASSIGNED_TO</text>
                                        <line markerEnd="url(#arrow-teal)" stroke="#008e97" strokeDasharray="2 2" strokeWidth="1.5" x1="20%" x2="50%" y1="60%" y2="50%"></line>
                                        <text dy="15" fill="#008e97" fontFamily="monospace" fontSize="9" textAnchor="middle" x="35%" y="55%">DERIVED_FROM</text>
                                    </svg>
                                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10 group cursor-pointer">
                                        <div className="bg-red-50 border border-primary text-primary px-3 py-1.5 rounded shadow-lg flex items-center gap-2 ring-4 ring-red-500/10 transition-all group-hover:ring-red-500/20">
                                            <span className="material-symbols-outlined text-[16px]">warning</span>
                                            <span className="text-[10px] font-bold font-mono">EVENT-402</span>
                                        </div>
                                        <span className="mt-1 text-[9px] font-medium text-text-sub bg-white/90 px-1.5 py-0.5 rounded backdrop-blur border border-border-light shadow-sm">Data Leakage</span>
                                    </div>
                                    <div className="absolute top-[30%] left-[75%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10">
                                        <div className="bg-white border-2 border-primary/50 text-text-main px-3 py-1.5 rounded-sm shadow-md flex items-center gap-2">
                                            <span className="material-symbols-outlined text-[16px] text-primary">gpp_bad</span>
                                            <span className="text-[10px] font-bold font-mono">CP-99</span>
                                        </div>
                                        <span className="mt-1 text-[9px] font-medium text-text-sub bg-white/90 px-1.5 py-0.5 rounded backdrop-blur border border-border-light shadow-sm">DLP Gateway</span>
                                    </div>
                                    <div className="absolute top-[20%] left-[25%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10">
                                        <div className="bg-teal-50 border border-lagoon text-lagoon px-3 py-1.5 rounded shadow-md flex items-center gap-2">
                                            <span className="material-symbols-outlined text-[16px]">policy</span>
                                            <span className="text-[10px] font-bold font-mono">POL-CYBER-01</span>
                                        </div>
                                    </div>
                                    <div className="absolute top-[80%] left-[50%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10">
                                        <div className="flex items-center gap-2 bg-white border border-border-dark px-2.5 py-1.5 rounded-full shadow-sm">
                                            <div className="w-5 h-5 bg-gray-100 rounded-full flex items-center justify-center border border-gray-200">
                                                <span className="material-symbols-outlined text-[14px] text-gray-500">person</span>
                                            </div>
                                            <span className="text-[10px] font-bold text-text-main">Risk Owner: IT Ops</span>
                                        </div>
                                    </div>
                                    <div className="absolute top-[60%] left-[20%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-10">
                                        <div className="bg-white border border-lagoon/30 text-text-sub px-2 py-1 rounded shadow-sm flex items-center gap-2">
                                            <span className="material-symbols-outlined text-[14px] text-lagoon">receipt_long</span>
                                            <span className="text-[9px] font-mono">SYS_LOG_88</span>
                                        </div>
                                    </div>
                                    <div className="absolute bottom-3 right-3 bg-white/95 backdrop-blur border border-border-light p-2.5 rounded shadow-sm flex flex-col gap-1.5 z-20">
                                        <div className="flex items-center gap-2">
                                            <span className="w-3 h-0.5 bg-primary"></span>
                                            <span className="text-[9px] text-text-sub font-mono uppercase">Critical Path</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="w-3 h-0.5 bg-lagoon"></span>
                                            <span className="text-[9px] text-text-sub font-mono uppercase">Info Flow</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
            <section className="py-10 bg-surface-light border-b border-border-light">
                <div className="max-w-[95%] mx-auto px-6">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-lg font-bold text-text-main uppercase tracking-tight">Data Tracked by Hypergraph</h2>
                        <div className="flex items-center gap-2 text-[10px] text-text-sub font-mono bg-white px-2 py-1 border border-border-light rounded-sm">
                            LAST_SYNC: {appConfig.meta.lastSync}
                        </div>
                    </div>
                    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                        <div className="bg-white p-4 rounded border border-border-light shadow-card hover:shadow-md transition-shadow group">
                            <div className="flex items-center gap-2 mb-3 text-text-sub group-hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-[18px]">bug_report</span>
                                <span className="text-xs font-medium">Issues</span>
                            </div>
                            <div className="text-2xl font-mono font-medium text-text-main mb-1 tracking-tight">{appConfig.stats.issues.count}</div>
                            <div className="flex items-center gap-1 text-[10px] font-mono text-green-600 bg-green-50 w-fit px-1.5 py-0.5 rounded">
                                <span className="material-symbols-outlined text-[12px]">arrow_upward</span>
                                <span>+{appConfig.stats.issues.ingested} Ingested</span>
                            </div>
                        </div>
                        <div className="bg-white p-4 rounded border border-border-light shadow-card hover:shadow-md transition-shadow group">
                            <div className="flex items-center gap-2 mb-3 text-text-sub group-hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-[18px]">gpp_good</span>
                                <span className="text-xs font-medium">Controls</span>
                            </div>
                            <div className="text-2xl font-mono font-medium text-text-main mb-1 tracking-tight">{appConfig.stats.controls.count}</div>
                            <div className="flex items-center gap-1 text-[10px] font-mono text-green-600 bg-green-50 w-fit px-1.5 py-0.5 rounded">
                                <span className="material-symbols-outlined text-[12px]">arrow_upward</span>
                                <span>+{appConfig.stats.controls.ingested} Ingested</span>
                            </div>
                        </div>
                        <div className="bg-white p-4 rounded border border-border-light shadow-card hover:shadow-md transition-shadow group">
                            <div className="flex items-center gap-2 mb-3 text-text-sub group-hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-[18px]">notifications_active</span>
                                <span className="text-xs font-medium">Events</span>
                            </div>
                            <div className="text-2xl font-mono font-medium text-text-main mb-1 tracking-tight">{appConfig.stats.events.count}</div>
                            <div className="flex items-center gap-1 text-[10px] font-mono text-green-600 bg-green-50 w-fit px-1.5 py-0.5 rounded">
                                <span className="material-symbols-outlined text-[12px]">arrow_upward</span>
                                <span>+{appConfig.stats.events.ingested} Ingested</span>
                            </div>
                        </div>
                        <div className="bg-white p-4 rounded border border-border-light shadow-card hover:shadow-md transition-shadow group">
                            <div className="flex items-center gap-2 mb-3 text-text-sub group-hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-[18px]">trending_down</span>
                                <span className="text-xs font-medium">External Loss</span>
                            </div>
                            <div className="text-2xl font-mono font-medium text-text-main mb-1 tracking-tight">{appConfig.stats.externalLoss.count}</div>
                            <div className="flex items-center gap-1 text-[10px] font-mono text-green-600 bg-green-50 w-fit px-1.5 py-0.5 rounded">
                                <span className="material-symbols-outlined text-[12px]">arrow_upward</span>
                                <span>+{appConfig.stats.externalLoss.ingested} Ingested</span>
                            </div>
                        </div>
                        <div className="bg-white p-4 rounded border border-border-light shadow-card hover:shadow-md transition-shadow group">
                            <div className="flex items-center gap-2 mb-3 text-text-sub group-hover:text-primary transition-colors">
                                <span className="material-symbols-outlined text-[18px]">policy</span>
                                <span className="text-xs font-medium">Policies</span>
                            </div>
                            <div className="text-2xl font-mono font-medium text-text-main mb-1 tracking-tight">{appConfig.stats.policies.count}</div>
                            <div className="flex items-center gap-1 text-[10px] font-mono text-green-600 bg-green-50 w-fit px-1.5 py-0.5 rounded">
                                <span className="material-symbols-outlined text-[12px]">arrow_upward</span>
                                <span>+{appConfig.stats.policies.ingested} Ingested</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
            <section className="py-16 bg-white border-b border-border-light overflow-hidden">
                <div className="max-w-[95%] mx-auto px-6">
                    <div className="mb-10 max-w-2xl">
                        <h2 className="text-2xl font-bold text-text-main tracking-tight mb-3">
                            Platform Capabilities
                        </h2>
                        <p className="text-text-sub text-sm leading-relaxed">
                            Advanced features powering the next generation of non-financial risk management.
                        </p>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                        {appConfig.features.map((feature, idx) => (
                            <div
                                key={idx}
                                className={`${feature.colSpan} relative rounded-sm bg-surface-light border border-border-light p-8 overflow-hidden group transition-all duration-200 ease-out h-[300px] flex flex-col justify-between hover:shadow-xl hover:border-primary/20`}
                                onMouseMove={handleMouseMove}
                                onMouseLeave={handleMouseLeave}
                                style={{ transformStyle: 'preserve-3d', willChange: 'transform' }}
                            >
                                <div className="absolute inset-0 bg-grid opacity-30 pointer-events-none"></div>
                                <div className={`absolute -right-10 -bottom-10 w-40 h-40 ${feature.color} opacity-10 blur-3xl rounded-full group-hover:opacity-20 transition-opacity`}></div>

                                <div className="relative z-10 translate-z-[20px]">
                                    <div className={`w-12 h-12 rounded-lg ${feature.color} bg-opacity-10 flex items-center justify-center mb-4`}>
                                        <span className={`material-symbols-outlined text-2xl ${feature.color.replace('bg-', 'text-')}`}>
                                            {feature.icon}
                                        </span>
                                    </div>
                                    <h3 className="text-xl font-bold text-text-main mb-2 group-hover:text-primary transition-colors">
                                        {feature.title}
                                    </h3>
                                    <p className="text-text-sub text-sm leading-relaxed max-w-[90%]">
                                        {feature.desc}
                                    </p>
                                </div>

                                <div className="relative z-10 flex items-center gap-2 text-xs font-semibold text-primary opacity-0 translate-y-4 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-300">
                                    <span>Learn more</span>
                                    <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
            <section className="py-12 bg-white border-b border-border-light">
                <div className="max-w-[95%] mx-auto px-6">
                    <div className="flex items-center justify-between mb-8">
                        <h2 className="text-lg font-bold text-text-main uppercase tracking-tight">Risk Models Portfolio</h2>
                        <div className="flex items-center gap-2">
                            <span className="text-[10px] font-medium text-text-sub">Portfolio Version: {appConfig.meta.portfolioVersion}</span>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {Object.values(appConfig.models).map((model) => (
                            <div key={model.id} className="bg-surface-light border border-border-light rounded-sm p-5 flex flex-col gap-4 hover:border-primary/40 transition-all group">
                                <div className="flex items-start justify-between">
                                    <div className="p-2 bg-white border border-border-light rounded shadow-sm">
                                        <span className="material-symbols-outlined text-primary text-[24px]">
                                            {model.id.includes('DICE') ? 'bubble_chart' : model.id.includes('HALO') ? 'account_tree' : 'psychology_alt'}
                                        </span>
                                    </div>
                                    <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold font-mono tracking-wider ${model.statusColor.bg} ${model.statusColor.text} border ${model.statusColor.border} uppercase`}>
                                        {model.status}
                                    </span>
                                </div>
                                <div className="flex-1">
                                    <h3 className="text-sm font-bold text-text-main leading-tight">{model.name}</h3>
                                    <p className="text-[11px] text-text-sub mt-1 leading-relaxed">{model.desc}</p>
                                </div>
                                <div className="pt-2 border-t border-border-light/60">
                                    <div className="flex justify-between items-center text-[10px] font-mono mb-3">
                                        <span className="text-text-sub">MRMP ID</span>
                                        <span className="font-bold text-text-main">{model.id}</span>
                                    </div>
                                    <a className="flex items-center justify-between px-3 py-2 bg-white border border-border-light rounded hover:bg-surface-hover hover:border-primary/40 transition-all text-xs font-medium text-text-main group/link" href="#">
                                        <span>{model.id.includes('AGNT') ? 'Development Roadmap' : model.id.includes('HALO') ? 'Technical Details' : 'Documentation'}</span>
                                        <span className="material-symbols-outlined text-[16px] text-text-sub group-hover/link:text-primary transition-colors">open_in_new</span>
                                    </a>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
            <section className="py-12 bg-surface-light border-b border-border-light">
                <div className="max-w-[95%] mx-auto px-6">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-lg font-bold text-text-main uppercase tracking-tight">NFR Connect Team</h2>
                        <button className="text-xs text-primary hover:underline font-medium flex items-center gap-1">
                            View Org Chart
                            <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                        </button>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {appConfig.team.map((member) => (
                            <div key={member.name} className="group flex items-center gap-3 p-3 bg-white rounded border border-border-light hover:border-primary/40 transition-all cursor-default hover:shadow-subtle">
                                <div className="w-10 h-10 rounded-full bg-white border border-border-light p-0.5 shadow-sm group-hover:shadow-md transition-shadow shrink-0">
                                    <div className="w-full h-full rounded-full bg-slate-200 flex items-center justify-center overflow-hidden">
                                        <span className="material-symbols-outlined text-slate-400 text-[18px]">{member.icon}</span>
                                    </div>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <h3 className="text-sm font-bold text-text-main leading-tight mb-0.5">{member.name}</h3>
                                    <p className="text-[10px] font-mono text-primary font-medium uppercase tracking-wide truncate">{member.role}</p>
                                </div>
                                <div className="flex gap-1.5">
                                    <button className="h-7 w-7 flex items-center justify-center rounded bg-surface-light border border-border-light text-text-sub hover:text-primary hover:border-primary transition-all">
                                        <span className="material-symbols-outlined text-[14px]">mail</span>
                                    </button>
                                    <button className="h-7 w-7 flex items-center justify-center rounded bg-surface-light border border-border-light text-text-sub hover:text-primary hover:border-primary transition-all">
                                        <span className="material-symbols-outlined text-[14px]">
                                            {member.role.includes('Developer') ? 'code' : member.role.includes('Scientist') ? 'analytics' : 'chat'}
                                        </span>
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
        </main>
    );
};

export default Home;
