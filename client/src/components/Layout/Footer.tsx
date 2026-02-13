import { useState, useEffect } from 'react';
import { appConfig } from '../../config/appConfig';

type HealthStatus = 'loading' | 'operational' | 'degraded';

const Footer = () => {
    const [status, setStatus] = useState<HealthStatus>('loading');

    useEffect(() => {
        const check = () => {
            fetch(`${appConfig.api.baseUrl}/api/v2/health`)
                .then(res => res.ok ? res.json() : null)
                .then(data => {
                    if (data?.status === 'healthy') setStatus('operational');
                    else setStatus('degraded');
                })
                .catch(() => setStatus('degraded'));
        };

        check();
        const interval = setInterval(check, 60_000);
        return () => clearInterval(interval);
    }, []);

    const statusConfig = {
        loading:     { color: 'bg-yellow-400', label: 'Checking...' },
        operational: { color: 'bg-green-500',  label: 'Operational' },
        degraded:    { color: 'bg-red-500',    label: 'Degraded' },
    };

    const { color, label } = statusConfig[status];

    return (
        <footer className="bg-white border-t border-border-light py-3">
            <div className="max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4">
                <div className="flex flex-col md:flex-row justify-between items-center gap-3 text-xs text-text-sub">
                    <div className="flex items-center gap-3">
                        <span className="font-semibold text-text-main">{appConfig.appName}</span>
                        <span className="text-border-light">|</span>
                        <span>&copy; 2024 UBS NFR Insights</span>
                    </div>
                    <div className="flex items-center gap-4">
                        {appConfig.team.slice(0, 3).map((member, idx) => (
                            <div key={member.role} className="flex items-center gap-1.5">
                                <span className="text-text-sub">{member.role}:</span>
                                <a href={`mailto:${member.name.toLowerCase().replace(' ', '.')}@ubs.com`} className="text-text-main hover:text-primary transition-colors">
                                    {member.name}
                                </a>
                                {idx < 2 && <span className="text-border-light ml-2">|</span>}
                            </div>
                        ))}
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-1.5 px-2 py-0.5 bg-surface-light rounded border border-border-light">
                            <span className={`w-1.5 h-1.5 rounded-full ${color}`}></span>
                            <span className="font-mono text-[10px]">{label}</span>
                        </div>
                    </div>
                </div>
            </div>
        </footer>
    );
};

export default Footer;
