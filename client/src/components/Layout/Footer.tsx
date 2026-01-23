import React from 'react';
import { appConfig } from '../../config/appConfig';

const Footer = () => {
    return (
        <footer className="bg-white border-t border-border-light py-8">
            <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-4 text-xs text-text-sub">
                <div className="flex items-center gap-4">
                    <span className="font-semibold text-text-main">{appConfig.appName}</span>
                    <span className="text-border-dark">|</span>
                    <span>© 2023 UBS NFR Insights. Internal Use Only.</span>
                </div>
                <div className="flex items-center gap-6">
                    <a className="hover:text-primary transition-colors" href="/privacy">Privacy Policy</a>
                    <a className="hover:text-primary transition-colors" href="/terms">Terms of Service</a>
                    <a className="hover:text-primary transition-colors" href="/support">Support</a>
                    <div className="flex items-center gap-2 px-2 py-1 bg-surface-light rounded border border-border-light">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                        <span className="font-mono text-[10px]">All Systems Operational</span>
                    </div>
                </div>
            </div>
        </footer>
    );
};

export default Footer;
