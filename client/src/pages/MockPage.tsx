import React from 'react';
import { Link } from 'react-router-dom';

interface MockPageProps {
    title?: string;
}

const MockPage: React.FC<MockPageProps> = ({ title = "Coming Soon" }) => {
    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-surface-light">
            <div className="text-center">
                <span className="material-symbols-outlined text-[48px] text-lagoon mb-4">engineering</span>
                <h1 className="text-2xl font-bold text-text-main mb-2">{title}</h1>
                <p className="text-text-sub mb-6">This feature is currently under development.</p>
                <Link to="/" className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-border-light rounded hover:bg-surface-hover text-sm font-medium text-text-main transition-colors">
                    <span className="material-symbols-outlined text-[16px]">home</span>
                    Back to Dashboard
                </Link>
            </div>
        </div>
    );
};

export default MockPage;
