import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { appConfig } from '../../config/appConfig';
import { useAuth } from '../../auth/useAuth';

const Header = () => {
    const location = useLocation();
    const { isAuthenticated, account, login, logout } = useAuth();

    const getInitials = (name: string) => {
        return name
            .split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .substring(0, 2);
    };

    return (
        <header className="fixed w-full top-0 z-50 bg-background-light/95 backdrop-blur-sm border-b border-border-light h-12 flex items-center justify-between px-6 shadow-sm">
            <div className="flex items-center gap-6">
                <div className="flex items-center gap-3">
                    <img
                        alt="UBS Logo"
                        className="h-6"
                        src={require('../../imgs/ubs_logo.svg').default}
                    />
                    <div className="h-4 w-px bg-border-light mx-1"></div>
                    <span className="font-semibold text-sm tracking-tight text-text-main">{appConfig.appName}</span>
                </div>
                <nav className="hidden md:flex items-center gap-1 ml-4">
                    <Link
                        to="/"
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors group ${location.pathname === '/'
                            ? 'text-primary bg-surface-light'
                            : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                            }`}
                    >
                        <span className={`material-symbols-outlined ${location.pathname === '/' ? 'text-primary' : 'text-text-sub group-hover:text-primary'}`}>
                            home
                        </span>
                        Home
                    </Link>
                    <Link
                        to="/docs"
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors group ${location.pathname === '/docs'
                            ? 'text-primary bg-surface-light'
                            : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                            }`}
                    >
                        <span className={`material-symbols-outlined ${location.pathname === '/docs' ? 'text-primary' : 'text-text-sub group-hover:text-primary'}`}>
                            article
                        </span>
                        Docs
                    </Link>
                    <Link
                        to="/dashboard"
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors group ${location.pathname === '/dashboard'
                            ? 'text-primary bg-surface-light'
                            : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                            } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                    >
                        <span className={`material-symbols-outlined ${location.pathname === '/dashboard' ? 'text-primary' : 'text-text-sub group-hover:text-primary'}`}>
                            dashboard
                        </span>
                        Dashboard
                    </Link>
                    <Link
                        to="/chat"
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors group ${location.pathname === '/chat'
                            ? 'text-primary bg-surface-light'
                            : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                            } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                    >
                        <span className={`material-symbols-outlined ${location.pathname === '/chat' ? 'text-primary' : 'text-text-sub group-hover:text-primary'}`}>
                            chat
                        </span>
                        Chat
                    </Link>
                    <Link
                        to="/glossary"
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors group ${location.pathname === '/glossary'
                            ? 'text-primary bg-surface-light'
                            : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                            } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                    >
                        <span className={`material-symbols-outlined ${location.pathname === '/glossary' ? 'text-primary' : 'text-text-sub group-hover:text-primary'}`}>
                            book
                        </span>
                        Glossary
                    </Link>
                    <Link
                        to="/one-off-features"
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors group ${location.pathname === '/one-off-features'
                            ? 'text-primary bg-surface-light'
                            : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                            } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                    >
                        <span className={`material-symbols-outlined ${location.pathname === '/one-off-features' ? 'text-primary' : 'text-text-sub group-hover:text-primary'}`}>
                            extension
                        </span>
                        OneOffFeatures
                    </Link>
                    <Link
                        to="/pipelines"
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors group ${location.pathname === '/pipelines'
                            ? 'text-primary bg-surface-light'
                            : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                            } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                    >
                        <span className={`material-symbols-outlined ${location.pathname === '/pipelines' ? 'text-primary' : 'text-text-sub group-hover:text-primary'}`}>
                            linear_scale
                        </span>
                        Pipelines
                    </Link>
                </nav>
            </div>
            <div className="flex items-center gap-3">
                {isAuthenticated ? (
                    <>
                        <button className="h-7 w-7 rounded bg-surface-light border border-border-light flex items-center justify-center text-text-sub hover:text-primary hover:border-primary transition-colors">
                            <span className="material-symbols-outlined">notifications</span>
                        </button>
                        <button className="h-7 w-7 rounded bg-surface-light border border-border-light flex items-center justify-center text-text-sub hover:text-primary hover:border-primary transition-colors">
                            <span className="material-symbols-outlined">settings</span>
                        </button>
                        <div
                            className="h-7 w-7 rounded bg-primary text-white flex items-center justify-center text-[10px] font-bold cursor-default shadow-sm"
                            title={account?.name || 'User'}
                        >
                            {account?.name ? getInitials(account.name) : 'JD'}
                        </div>
                        <button
                            onClick={() => logout()}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-light hover:bg-surface-hover border border-border-light text-text-sub hover:text-text-main text-xs font-medium rounded transition-colors"
                        >
                            <span className="material-symbols-outlined text-[14px]">logout</span>
                            <span>Sign Out</span>
                        </button>
                    </>
                ) : (
                    <button
                        onClick={() => login()}
                        className="flex items-center gap-2 px-3 py-1.5 bg-white hover:bg-surface-hover text-text-main text-xs font-medium rounded transition-colors border border-border-light shadow-sm"
                        title="Sign In with Microsoft"
                    >
                        <img
                            src={require('../../imgs/microsoft.svg').default}
                            alt=""
                            className="w-3.5 h-3.5"
                        />
                        <span>Sign In</span>
                    </button>
                )}
            </div>
        </header>
    );
};

export default Header;
