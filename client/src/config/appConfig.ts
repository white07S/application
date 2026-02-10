export const appConfig = {
    appName: 'NFR Connect',
    appVersion: 'v3.1.0 Connected Intelligence',
    externalLinks: {
        github: process.env.REACT_APP_GITHUB_URL || "",
        issueTracker: process.env.REACT_APP_ISSUE_TRACKER_URL || "",
    },
    auth: {
        clientId: process.env.REACT_APP_CLIENT_ID || "6c0e6344-99f5-49ee-b089-a754f3f1e807",
        authority: process.env.REACT_APP_AUTHORITY || "https://login.microsoftonline.com/cd047842-758c-4a08-84eb-36bed37ec49e",
        redirectUri: process.env.REACT_APP_REDIRECT_URI || "http://localhost:3000",
        loginScopes: (process.env.REACT_APP_LOGIN_SCOPES || "User.Read").split(','),
        apiScopes: (process.env.REACT_APP_API_SCOPES || "api://5dd696a4-03e2-4fb4-a19e-0b58e11a0c7a/access_as_user").split(','),
        graphEndpoint: process.env.REACT_APP_GRAPH_ENDPOINT || "https://graph.microsoft.com/v1.0/me",
    },
    api: {
        baseUrl: process.env.REACT_APP_API_BASE_URL || "http://localhost:8000",
    },
    stats: {
        riskEntities: '4,281',
        activeAgents: '12',
        nodesMapped: '150M+',
        issues: {
            count: '3,892',
            ingested: '142',
        },
        controls: {
            count: '12,482',
            ingested: '245',
        },
        events: {
            count: '85,201',
            ingested: '892',
        },
        externalLoss: {
            count: '412',
            ingested: '12',
        },
        policies: {
            count: '1,024',
            ingested: '56',
        },
    },
    meta: {
        lastSync: '14:02:44 UTC',
    },
    models: {
        dice: {
            id: 'DICE-9921',
            name: 'NFR DICE',
            desc: 'Data Insights Clustering Enrichment for automated taxonomy mapping.',
            status: 'Live',
            statusColor: {
                bg: 'bg-green-100',
                text: 'text-green-700',
                border: 'border-green-200'
            }
        },
        halo: {
            id: 'HALO-4810',
            name: 'NFR HALO',
            desc: 'Hypergraph Analysis of Linked Objects for multi-hop risk propagation.',
            status: 'Validation',
            statusColor: {
                bg: 'bg-blue-100',
                text: 'text-blue-700',
                border: 'border-blue-200'
            }
        },
        agent: {
            id: 'AGNT-2234',
            name: 'NFR AGENT',
            desc: 'Agent Orchestration for reasoning over unstructured risk signals.',
            status: 'In Progress',
            statusColor: {
                bg: 'bg-orange-100',
                text: 'text-orange-700',
                border: 'border-orange-200'
            }
        }
    },
    features: [
        {
            title: "Agentic Reasoning",
            desc: "Autonomous LLM agents that reason over complex unstructured data to identify risks, providing deep insights beyond simple pattern matching.",
            icon: "psychology",
            color: "bg-purple-500",
            colSpan: "col-span-1 lg:col-span-8"
        },
        {
            title: "Graph Visualization",
            desc: "Interactive knowledge graph usage to visualize hidden relationships and propagation paths.",
            icon: "hub",
            color: "bg-blue-500",
            colSpan: "col-span-1 lg:col-span-4"
        },
        {
            title: "Automated Taxonomy",
            desc: "DICE model automatically maps control failures to the correct risk taxonomy nodes.",
            icon: "account_tree",
            color: "bg-green-500",
            colSpan: "col-span-1 lg:col-span-4"
        },
        {
            title: "Real-time Monitoring",
            desc: "Live tracking of risk signals and control effectiveness across the entire enterprise landscape.",
            icon: "speed",
            color: "bg-red-500",
            colSpan: "col-span-1 lg:col-span-4"
        },
        {
            title: "Smart Reporting",
            desc: "Generate comprehensive risk posture reports instantly using generative AI.",
            icon: "description",
            color: "bg-orange-500",
            colSpan: "col-span-1 lg:col-span-4"
        }
    ],
    team: [
        {
            name: 'Tanja Weiher',
            role: 'Model Sponsor',
            icon: 'person'
        },
        {
            name: 'Zhi Chung',
            role: 'Model Owner',
            icon: 'person_3'
        },
        {
            name: 'Preetam Sharma',
            role: 'Lead Developer',
            icon: 'person_4'
        }
    ]
};
