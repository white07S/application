import React from 'react';
import Home from '../pages/Home/Home';
import MockPage from '../pages/MockPage';
import Unauthorized from '../pages/Unauthorized';
// Determine if we should lazy load real components or use mocks based on file existence/requirement
// For now, implementing requested structure

export interface RouteConfig {
    path: string;
    component: React.ComponentType<any>;
    name: string;
    protected: boolean;
    requiredRole?: string[]; // RBAC if needed
    accessRight?: string;   // For granular ABAC (e.g., 'hasChatAccess')
    hideInNav?: boolean;
}

export const routes: RouteConfig[] = [
    {
        path: "/",
        component: Home,
        name: "Home",
        protected: false, // Public as requested
    },
    {
        path: "/docs",
        component: () => <MockPage title="Documentation" />,
        name: "Docs",
        protected: false, // Public as requested
    },
    {
        path: "/dashboard",
        component: () => <MockPage title="Dashboard" />,
        name: "Dashboard",
        protected: true,
        accessRight: "hasDashboardAccess",
    },
    {
        path: "/chat",
        component: () => <MockPage title="Chat" />,
        name: "Chat",
        protected: true,
        accessRight: "hasChatAccess",
    },
    {
        path: "/glossary",
        component: () => <MockPage title="Glossary" />,
        name: "Glossary",
        protected: true,
    },
    {
        path: "/one-off-features",
        component: () => <MockPage title="One Off Features" />,
        name: "OneOffFeatures",
        protected: true,
    },
    {
        path: "/pipelines",
        component: () => <MockPage title="Pipelines" />,
        name: "Pipelines",
        protected: true,
    },
    {
        path: "/unauthorized",
        component: Unauthorized,
        name: "Unauthorized",
        protected: false,
        hideInNav: true,
    }
];
