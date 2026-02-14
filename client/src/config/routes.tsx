import React from 'react';
import Home from '../pages/Home/Home';
import MockPage from '../pages/MockPage';
import Unauthorized from '../pages/Unauthorized';
import DocsPage from '../pages/Docs/DocsPage';
import Pipelines from '../pages/Pipelines/Pipelines';
import Processing from '../pages/Pipelines/Processing';
import DevDataLayout from '../pages/DevData/DevDataLayout';
import ExplorerLayout from '../pages/Explorer/ExplorerLayout';

export interface RouteConfig {
    path: string;
    component: React.ComponentType<any>;
    name: string;
    protected: boolean;
    accessRight?: string;   // For granular ABAC (e.g., 'hasChatAccess')
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
    },
    {
        path: "/explorer",
        component: ExplorerLayout,
        name: "Explorer",
        protected: true,
        accessRight: "hasExplorerAccess",
    },
    {
        path: "/explorer/controls",
        component: ExplorerLayout,
        name: "Explorer - Controls",
        protected: true,
        accessRight: "hasExplorerAccess",
    },
    {
        path: "/explorer/events",
        component: ExplorerLayout,
        name: "Explorer - Events",
        protected: true,
        accessRight: "hasExplorerAccess",
    },
    {
        path: "/explorer/issues",
        component: ExplorerLayout,
        name: "Explorer - Issues",
        protected: true,
        accessRight: "hasExplorerAccess",
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
        path: "/pipelines/upload",
        component: Pipelines,
        name: "Pipelines",
        protected: true,
        accessRight: "hasPipelinesIngestionAccess",
    },
    {
        path: "/pipelines/ingestion",
        component: Processing,
        name: "Ingestion",
        protected: true,
        accessRight: "hasPipelinesIngestionAccess",
    },
    {
        path: "/devdata",
        component: DevDataLayout,
        name: "Dev Data",
        protected: true,
        accessRight: "hasDevDataAccess",
    },
    {
        path: "/devdata/:tableName",
        component: DevDataLayout,
        name: "Dev Data",
        protected: true,
        accessRight: "hasDevDataAccess",
    },
    {
        path: "/unauthorized",
        component: Unauthorized,
        name: "Unauthorized",
        protected: false,
    }
];
