import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { appConfig } from '../../config/appConfig';
import { useAuth } from '../../auth/useAuth';

const Header = () => {
    const location = useLocation();
    const { isAuthenticated, account, login, logout } = useAuth();
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const mobileMenuRef = useRef<HTMLDivElement>(null);

    // Close mobile menu on route change
    useEffect(() => {
        setIsMobileMenuOpen(false);
    }, [location.pathname]);

    // Close mobile menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (mobileMenuRef.current && !mobileMenuRef.current.contains(event.target as Node)) {
                setIsMobileMenuOpen(false);
            }
        };

        if (isMobileMenuOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isMobileMenuOpen]);

    // Close mobile menu on escape key
    useEffect(() => {
        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setIsMobileMenuOpen(false);
            }
        };

        if (isMobileMenuOpen) {
            document.addEventListener('keydown', handleEscape);
        }

        return () => {
            document.removeEventListener('keydown', handleEscape);
        };
    }, [isMobileMenuOpen]);

    const getInitials = (name: string) => {
        return name
            .split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .substring(0, 2);
    };

    return (
        <header className="fixed inset-x-0 top-0 z-50 bg-background-light/95 backdrop-blur-sm border-b border-border-light h-12 shadow-sm">
            <div className="max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] mx-auto px-3 sm:px-4 h-full flex items-center justify-between">
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
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors group ${location.pathname.startsWith('/docs')
                            ? 'text-primary bg-surface-light'
                            : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                            }`}
                    >
                        <span className={`material-symbols-outlined ${location.pathname.startsWith('/docs') ? 'text-primary' : 'text-text-sub group-hover:text-primary'}`}>
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
                        to="/pipelines/ingestion"
                        className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors group ${location.pathname.startsWith('/pipelines')
                            ? 'text-primary bg-surface-light'
                            : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                            } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                    >
                        <span className={`material-symbols-outlined ${location.pathname.startsWith('/pipelines') ? 'text-primary' : 'text-text-sub group-hover:text-primary'}`}>
                            linear_scale
                        </span>
                        Pipelines
                    </Link>
                </nav>
            </div>
            <div className="flex items-center gap-3">
                {/* Mobile hamburger menu button */}
                <button
                    className="flex md:hidden items-center justify-center h-8 w-8 rounded text-text-sub hover:text-primary hover:bg-surface-light transition-colors"
                    onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                    aria-label={isMobileMenuOpen ? 'Close menu' : 'Open menu'}
                    aria-expanded={isMobileMenuOpen}
                >
                    {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
                </button>

                {isAuthenticated ? (
                    <>
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

            {/* Mobile Navigation Menu */}
            {isMobileMenuOpen && (
                <div
                    ref={mobileMenuRef}
                    className="md:hidden fixed top-12 left-0 right-0 bg-white border-b border-border-light shadow-md z-40"
                >
                    <nav className="flex flex-col gap-1 p-3">
                        <div className="flex items-center justify-between pb-2 mb-1 border-b border-border-light">
                            <span className="text-xs font-medium text-text-sub">Navigation</span>
                            <button
                                onClick={() => setIsMobileMenuOpen(false)}
                                className="flex items-center justify-center h-7 w-7 rounded text-text-sub hover:text-primary hover:bg-surface-light transition-colors"
                                aria-label="Close menu"
                            >
                                <X size={16} />
                            </button>
                        </div>
                        <Link
                            to="/"
                            className={`flex items-center gap-2 px-3 py-2 min-h-[44px] text-sm font-medium rounded transition-colors ${location.pathname === '/'
                                ? 'text-primary bg-surface-light'
                                : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                                }`}
                            onClick={() => setIsMobileMenuOpen(false)}
                        >
                            <span className={`material-symbols-outlined ${location.pathname === '/' ? 'text-primary' : 'text-text-sub'}`}>
                                home
                            </span>
                            Home
                        </Link>
                        <Link
                            to="/docs"
                            className={`flex items-center gap-2 px-3 py-2 min-h-[44px] text-sm font-medium rounded transition-colors ${location.pathname.startsWith('/docs')
                                ? 'text-primary bg-surface-light'
                                : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                                }`}
                            onClick={() => setIsMobileMenuOpen(false)}
                        >
                            <span className={`material-symbols-outlined ${location.pathname.startsWith('/docs') ? 'text-primary' : 'text-text-sub'}`}>
                                article
                            </span>
                            Docs
                        </Link>
                        <Link
                            to="/dashboard"
                            className={`flex items-center gap-2 px-3 py-2 min-h-[44px] text-sm font-medium rounded transition-colors ${location.pathname === '/dashboard'
                                ? 'text-primary bg-surface-light'
                                : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                                } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                            onClick={() => setIsMobileMenuOpen(false)}
                        >
                            <span className={`material-symbols-outlined ${location.pathname === '/dashboard' ? 'text-primary' : 'text-text-sub'}`}>
                                dashboard
                            </span>
                            Dashboard
                            {!isAuthenticated && <span className="text-[10px] text-text-sub ml-auto">(Sign in required)</span>}
                        </Link>
                        <Link
                            to="/chat"
                            className={`flex items-center gap-2 px-3 py-2 min-h-[44px] text-sm font-medium rounded transition-colors ${location.pathname === '/chat'
                                ? 'text-primary bg-surface-light'
                                : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                                } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                            onClick={() => setIsMobileMenuOpen(false)}
                        >
                            <span className={`material-symbols-outlined ${location.pathname === '/chat' ? 'text-primary' : 'text-text-sub'}`}>
                                chat
                            </span>
                            Chat
                            {!isAuthenticated && <span className="text-[10px] text-text-sub ml-auto">(Sign in required)</span>}
                        </Link>
                        <Link
                            to="/glossary"
                            className={`flex items-center gap-2 px-3 py-2 min-h-[44px] text-sm font-medium rounded transition-colors ${location.pathname === '/glossary'
                                ? 'text-primary bg-surface-light'
                                : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                                } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                            onClick={() => setIsMobileMenuOpen(false)}
                        >
                            <span className={`material-symbols-outlined ${location.pathname === '/glossary' ? 'text-primary' : 'text-text-sub'}`}>
                                book
                            </span>
                            Glossary
                            {!isAuthenticated && <span className="text-[10px] text-text-sub ml-auto">(Sign in required)</span>}
                        </Link>
                        <Link
                            to="/one-off-features"
                            className={`flex items-center gap-2 px-3 py-2 min-h-[44px] text-sm font-medium rounded transition-colors ${location.pathname === '/one-off-features'
                                ? 'text-primary bg-surface-light'
                                : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                                } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                            onClick={() => setIsMobileMenuOpen(false)}
                        >
                            <span className={`material-symbols-outlined ${location.pathname === '/one-off-features' ? 'text-primary' : 'text-text-sub'}`}>
                                extension
                            </span>
                            OneOffFeatures
                            {!isAuthenticated && <span className="text-[10px] text-text-sub ml-auto">(Sign in required)</span>}
                        </Link>
                        <Link
                            to="/pipelines/ingestion"
                            className={`flex items-center gap-2 px-3 py-2 min-h-[44px] text-sm font-medium rounded transition-colors ${location.pathname.startsWith('/pipelines')
                                ? 'text-primary bg-surface-light'
                                : 'text-text-sub hover:text-text-main hover:bg-surface-light'
                                } ${!isAuthenticated ? 'opacity-50 pointer-events-none grayscale' : ''}`}
                            onClick={() => setIsMobileMenuOpen(false)}
                        >
                            <span className={`material-symbols-outlined ${location.pathname.startsWith('/pipelines') ? 'text-primary' : 'text-text-sub'}`}>
                                linear_scale
                            </span>
                            Pipelines
                            {!isAuthenticated && <span className="text-[10px] text-text-sub ml-auto">(Sign in required)</span>}
                        </Link>
                    </nav>
                </div>
            )}
            </div>
        </header>
    );
};

export default Header;
