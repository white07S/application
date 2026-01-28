import React from 'react';
import Home from '../pages/Home/Home';
import MockPage from '../pages/MockPage';
import Unauthorized from '../pages/Unauthorized';
import DocsPage from '../pages/Docs/DocsPage';
import Pipelines from '../pages/Pipelines/Pipelines';
import Processing from '../pages/Pipelines/Processing';

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
        component: DocsPage,
        name: "Docs",
        protected: false,
    },
    {
        path: "/docs/*",
        component: DocsPage,
        name: "Docs",
        protected: false,
        hideInNav: true,
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
        path: "/pipelines/ingestion",
        component: Pipelines,
        name: "Pipelines",
        protected: true,
        accessRight: "hasPipelinesIngestionAccess",
    },
    {
        path: "/pipelines/processing",
        component: Processing,
        name: "Processing",
        protected: true,
        accessRight: "hasPipelinesIngestionAccess",
        hideInNav: true,
    },
    {
        path: "/unauthorized",
        component: Unauthorized,
        name: "Unauthorized",
        protected: false,
        hideInNav: true,
    }
];
