import { TreeNode, FlatItem, RiskTaxonomy } from './types';

export const mockFunctions: TreeNode[] = [
    {
        id: 'gf-1',
        label: 'Investment Banking',
        level: 0,
        children: [
            {
                id: 'f-1-1',
                label: 'Advisory',
                level: 1,
                children: [
                    { id: 'sf-1-1-1', label: 'M&A Advisory', level: 2 },
                    { id: 'sf-1-1-2', label: 'Capital Markets Advisory', level: 2 },
                ],
            },
            {
                id: 'f-1-2',
                label: 'Underwriting',
                level: 1,
                children: [
                    { id: 'sf-1-2-1', label: 'Equity Underwriting', level: 2 },
                    { id: 'sf-1-2-2', label: 'Debt Underwriting', level: 2 },
                ],
            },
        ],
    },
    {
        id: 'gf-2',
        label: 'Global Wealth Management',
        level: 0,
        children: [
            {
                id: 'f-2-1',
                label: 'Private Clients',
                level: 1,
                children: [
                    { id: 'sf-2-1-1', label: 'Ultra High Net Worth', level: 2 },
                    { id: 'sf-2-1-2', label: 'High Net Worth', level: 2 },
                ],
            },
            {
                id: 'f-2-2',
                label: 'Institutional Clients',
                level: 1,
            },
        ],
    },
    {
        id: 'gf-3',
        label: 'Asset Management',
        level: 0,
        children: [
            { id: 'f-3-1', label: 'Equities', level: 1 },
            { id: 'f-3-2', label: 'Fixed Income', level: 1 },
            { id: 'f-3-3', label: 'Multi-Asset', level: 1 },
        ],
    },
];

export const mockLocations: TreeNode[] = [
    {
        id: 'r-1',
        label: 'EMEA',
        level: 0,
        children: [
            {
                id: 'c-1-1',
                label: 'Switzerland',
                level: 1,
                children: [
                    { id: 'ci-1-1-1', label: 'Zurich', level: 2 },
                    { id: 'ci-1-1-2', label: 'Basel', level: 2 },
                    { id: 'ci-1-1-3', label: 'Geneva', level: 2 },
                ],
            },
            {
                id: 'c-1-2',
                label: 'United Kingdom',
                level: 1,
                children: [
                    { id: 'ci-1-2-1', label: 'London', level: 2 },
                ],
            },
            {
                id: 'c-1-3',
                label: 'Germany',
                level: 1,
                children: [
                    { id: 'ci-1-3-1', label: 'Frankfurt', level: 2 },
                ],
            },
        ],
    },
    {
        id: 'r-2',
        label: 'Americas',
        level: 0,
        children: [
            {
                id: 'c-2-1',
                label: 'United States',
                level: 1,
                children: [
                    { id: 'ci-2-1-1', label: 'New York', level: 2 },
                    { id: 'ci-2-1-2', label: 'Stamford', level: 2 },
                ],
            },
        ],
    },
    {
        id: 'r-3',
        label: 'APAC',
        level: 0,
        children: [
            {
                id: 'c-3-1',
                label: 'Hong Kong',
                level: 1,
            },
            {
                id: 'c-3-2',
                label: 'Singapore',
                level: 1,
            },
            {
                id: 'c-3-3',
                label: 'Japan',
                level: 1,
                children: [
                    { id: 'ci-3-3-1', label: 'Tokyo', level: 2 },
                ],
            },
        ],
    },
];

export const mockCEs: FlatItem[] = [
    { id: 'ce-1', label: 'UBS AG', description: 'Parent entity' },
    { id: 'ce-2', label: 'UBS Switzerland AG', description: 'Swiss retail & corporate' },
    { id: 'ce-3', label: 'UBS Europe SE', description: 'European operations' },
    { id: 'ce-4', label: 'UBS Securities LLC', description: 'US broker-dealer' },
    { id: 'ce-5', label: 'UBS Asset Management AG', description: 'Asset management' },
    { id: 'ce-6', label: 'UBS Financial Services Inc.', description: 'US wealth management' },
    { id: 'ce-7', label: 'UBS Bank (China) Ltd', description: 'China operations' },
    { id: 'ce-8', label: 'UBS Global Asset Management', description: 'Global AM' },
];

export const mockAUs: FlatItem[] = [
    { id: 'au-1', label: 'GWM Americas' },
    { id: 'au-2', label: 'GWM EMEA' },
    { id: 'au-3', label: 'GWM APAC' },
    { id: 'au-4', label: 'IB Global Markets' },
    { id: 'au-5', label: 'AM Equities' },
    { id: 'au-6', label: 'P&C Switzerland' },
];

export const mockRiskTaxonomies: RiskTaxonomy[] = [
    {
        id: 'tax-1',
        name: 'Operational Risk',
        themes: [
            { id: 'rt-1-1', name: 'Process Execution', status: 'active', children: [
                { id: 'rt-1-1-exp', name: 'Process Execution & Delivery', status: 'expired', children: [] },
            ] },
            { id: 'rt-1-2', name: 'Technology Failure', status: 'active', children: [] },
            { id: 'rt-1-3', name: 'Third-Party Risk', status: 'active', children: [] },
            { id: 'rt-1-4', name: 'Data Management', status: 'active', children: [] },
        ],
    },
    {
        id: 'tax-2',
        name: 'Compliance Risk',
        themes: [
            { id: 'rt-2-1', name: 'Regulatory Change', status: 'active', children: [] },
            { id: 'rt-2-2', name: 'Financial Crime', status: 'active', children: [] },
            { id: 'rt-2-3', name: 'Conduct Risk', status: 'active', children: [] },
        ],
    },
    {
        id: 'tax-3',
        name: 'Financial Risk',
        themes: [
            { id: 'rt-3-1', name: 'Credit Risk', status: 'active', children: [] },
            { id: 'rt-3-2', name: 'Market Risk', status: 'active', children: [] },
            { id: 'rt-3-3', name: 'Liquidity Risk', status: 'active', children: [] },
        ],
    },
];
