import React from 'react';
import { Link } from 'react-router-dom';

const Unauthorized = () => {
    return (
        <div className="min-h-screen flex flex-col justify-center py-12 sm:px-6 lg:px-8 bg-surface-light">
            <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
                <span className="material-symbols-outlined text-[48px] text-primary mb-4">gpp_bad</span>
                <h2 className="text-3xl font-extrabold text-text-main">Access Denied</h2>
                <p className="mt-2 text-sm text-text-sub">
                    You do not have the required permissions to view this page.
                </p>
                <div className="mt-6">
                    <Link to="/" className="text-sm font-medium text-primary hover:text-[#cc0000] flex items-center justify-center gap-1">
                        <span className="material-symbols-outlined text-[16px]">arrow_back</span>
                        Return to Home
                    </Link>
                </div>
            </div>
        </div>
    );
};

export default Unauthorized;
