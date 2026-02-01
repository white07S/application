# Controls Command Center - Implementation Plan

## Executive Summary

This document outlines the step-by-step implementation plan for the **Controls Command Center**, a comprehensive risk management dashboard built on top of the existing NFR Connect infrastructure. The plan is divided into two major phases:

1. **Phase 1: UI with Mock Data** - Build the complete frontend with static/mock data
2. **Phase 2: Backend Integration** - Connect to SurrealDB via API endpoints designed as MCP tools for agent consumption

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Recommended Libraries & Tech Stack](#2-recommended-libraries--tech-stack)
3. [Architecture Overview](#3-architecture-overview)
4. [Controls Layout Shell - Deep Dive](#4-controls-layout-shell---deep-dive)
5. [Phase 1: UI Implementation with Mock Data](#5-phase-1-ui-implementation-with-mock-data)
6. [Phase 2: Backend Integration & MCP Tools](#6-phase-2-backend-integration--mcp-tools)
7. [Component Specifications](#7-component-specifications)
8. [Mock Data Strategy](#8-mock-data-strategy)
9. [Testing Strategy](#9-testing-strategy)
10. [Risk & Dependencies](#10-risk--dependencies)

---

## 1. Current State Analysis

### 1.1 Existing Frontend Stack
- **Framework**: React 19.2.3 + TypeScript 4.9.5
- **Styling**: Tailwind CSS 3.4.19 with custom design system
- **Auth**: Azure AD via MSAL (@azure/msal-react)
- **State**: React Context + hooks (no Redux/Zustand in current pages)
- **Icons**: Lucide React + Material Symbols
- **Routing**: React Router DOM 7.12.0

### 1.2 Existing Backend Stack
- **Framework**: FastAPI (Python 3.12+)
- **Database**: SurrealDB (graph-enabled temporal database)
- **Package Manager**: UV (not pip)
- **Job Tracking**: SQLite for pipeline jobs

### 1.3 Existing Data Model (SurrealDB)

**Source Tables:**
- `src_controls_main` - Main control records with nested objects
- `src_controls_versions` - Version history snapshots
- `src_controls_ref_*` - Reference tables (risk_theme, org_function, org_location, sox_assertion, category_flag)
- `src_controls_rel_*` - Graph relationship edges

**AI Model Tables:**
- `ai_controls_model_taxonomy_current/versions` - NFR taxonomy classification
- `ai_controls_model_enrichment_current/versions` - 5W analysis + entity extraction
- `ai_controls_model_cleaned_text_current/versions` - Cleaned text with FTS indexes
- `ai_controls_model_embeddings_current/versions` - 3072-dim vector embeddings

**Existing Capabilities:**
- Graph traversal queries (control → relationships)
- Temporal "as-of-date" queries with fallback logic
- Full-text search with BM25 + highlights
- Version history tracking

### 1.4 Design System Constants

```typescript
// Colors (from tailwind.config.js)
const colors = {
  primary: '#e60000',      // UBS Red
  lagoon: '#008e97',       // Teal
  curry: '#EFC900',        // Yellow/Warning
  surfaceLight: '#f9f9f7',
  textMain: '#1c1c1c',
  textSub: '#4b5563',
  borderLight: '#e5e7eb',
};

// Typography: 10-12px base, compact information-dense design
// Spacing: 4px base unit
// Border radius: 2px (minimal modern)
```

---

## 2. Recommended Libraries & Tech Stack

This section outlines the specific libraries to use for building the Controls Command Center dashboard.

### 2.1 Charting & Data Visualization

#### Primary: Apache ECharts + echarts-for-react

**Installation:**
```bash
npm install echarts echarts-for-react
```

**Why ECharts:**
- **Performance**: Supports WebGL rendering for handling 100K+ data points efficiently
- **Rich Chart Types**: 50+ chart types including heatmaps, treemaps, Sankey diagrams
- **Enterprise Features**: Tooltips, data zoom, drill-down, brushing, animations
- **Active Maintenance**: Backed by Apache Foundation with regular updates

**Usage Pattern:**
```typescript
import ReactECharts from 'echarts-for-react';
import { useMemo } from 'react';

function HeatmapChart({ data, onCellClick }) {
  // CRITICAL: Memoize options to prevent re-renders
  const options = useMemo(() => ({
    tooltip: { position: 'top' },
    grid: { height: '50%', top: '10%' },
    xAxis: { type: 'category', data: xLabels },
    yAxis: { type: 'category', data: yLabels },
    visualMap: { min: 0, max: 100, calculable: true },
    series: [{
      type: 'heatmap',
      data: data,
      emphasis: { itemStyle: { shadowBlur: 10 } }
    }]
  }), [data, xLabels, yLabels]);

  return (
    <ReactECharts
      option={options}
      style={{ height: 400 }}
      onEvents={{ click: onCellClick }}
      opts={{ renderer: 'canvas' }} // or 'svg' for smaller datasets
    />
  );
}
```

**ECharts Best Practices:**
1. Always wrap `option` in `useMemo()` to prevent flicker
2. Use Canvas renderer for large datasets, SVG for smaller ones
3. Implement lazy loading for dashboard with multiple charts
4. Use `dataset` property for heatmaps instead of inline `series.data`

**References:**
- [ECharts Examples Gallery](https://echarts.apache.org/examples/en/index.html)
- [echarts-for-react npm](https://www.npmjs.com/package/echarts-for-react)
- [ECharts Heatmap with Dataset](https://blog.niuruihua.com/2023/08/23/Using-dataset-property-for-heatmap-chart-in-echarts-with-react)

---

### 2.2 Data Grid / Table

#### Primary: TanStack Table + TanStack Virtual

**Installation:**
```bash
npm install @tanstack/react-table @tanstack/react-virtual
```

**Why TanStack Table:**
- **Headless**: Full control over markup and styles (works with Tailwind)
- **Feature-Rich**: Sorting, filtering, grouping, column resizing, row selection
- **Virtualization**: TanStack Virtual handles 100K+ rows at 60fps
- **TypeScript-First**: Excellent type safety
- **Free**: MIT licensed, no commercial restrictions

**Why NOT AG Grid / MUI X:**
- AG Grid Enterprise features require $999+ license
- MUI X Data Grid ties you to Material Design
- TanStack gives more flexibility with your existing Tailwind design system

**Usage Pattern:**
```typescript
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';

function ControlsDataGrid({ data, columns }) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  // Virtualization for large datasets
  const { rows } = table.getRowModel();
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48, // row height
    overscan: 10,
  });

  return (
    <div ref={parentRef} className="h-[600px] overflow-auto">
      <table className="w-full">
        {/* Render only visible rows */}
        {virtualizer.getVirtualItems().map(virtualRow => {
          const row = rows[virtualRow.index];
          return <tr key={row.id}>...</tr>;
        })}
      </table>
    </div>
  );
}
```

**References:**
- [TanStack Table Docs](https://tanstack.com/table/latest)
- [TanStack Virtual Docs](https://tanstack.com/virtual/latest)
- [Virtualized Infinite Scrolling Example](https://tanstack.com/table/latest/docs/framework/react/examples/virtualized-infinite-scrolling)

---

### 2.3 Date Picker

#### Primary: react-day-picker (via Shadcn Calendar)

**Installation:**
```bash
npm install react-day-picker date-fns
# Or if using Shadcn:
npx shadcn@latest add calendar
```

**Why react-day-picker:**
- **6M+ weekly downloads** - battle-tested and reliable
- **Accessible**: WCAG 2.1 AA compliant
- **Customizable**: Full control over styling with Tailwind
- **date-fns based**: Lightweight date manipulation
- **Shadcn compatible**: If you add Shadcn later, it uses this underneath

**Custom AsOfDatePicker Implementation:**
```typescript
import { DayPicker } from 'react-day-picker';
import { format, parseISO } from 'date-fns';
import 'react-day-picker/dist/style.css';

interface AsOfDatePickerProps {
  value: AsOfSpec;
  onChange: (spec: AsOfSpec) => void;
  resolvedTo?: string;
}

function AsOfDatePicker({ value, onChange, resolvedTo }: AsOfDatePickerProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      {/* Mode Toggle */}
      <div className="flex items-center gap-2 mb-2">
        <button
          className={`px-3 py-1 text-xs rounded ${value.mode === 'CURRENT' ? 'bg-primary text-white' : 'bg-gray-100'}`}
          onClick={() => onChange({ ...value, mode: 'CURRENT', date: null })}
        >
          Current
        </button>
        <button
          className={`px-3 py-1 text-xs rounded ${value.mode === 'DATE' ? 'bg-primary text-white' : 'bg-gray-100'}`}
          onClick={() => setIsOpen(true)}
        >
          Historical
        </button>
      </div>

      {/* Date Picker Popover */}
      {isOpen && value.mode === 'DATE' && (
        <div className="absolute z-50 bg-white border shadow-lg rounded p-2">
          <DayPicker
            mode="single"
            selected={value.date ? parseISO(value.date) : undefined}
            onSelect={(date) => {
              onChange({ ...value, mode: 'DATE', date: format(date, 'yyyy-MM-dd') });
              setIsOpen(false);
            }}
            disabled={{ after: new Date() }} // Can't select future dates
          />
        </div>
      )}

      {/* Resolution Display */}
      {resolvedTo && (
        <div className="text-[10px] text-text-sub bg-surface-light px-2 py-1 rounded">
          Resolved to: {format(parseISO(resolvedTo), 'yyyy-MM-dd HH:mm:ss')}
        </div>
      )}
    </div>
  );
}
```

**References:**
- [React DayPicker Docs](https://daypicker.dev/)
- [Shadcn Calendar Component](https://ui.shadcn.com/docs/components/calendar)

---

### 2.4 State Management

#### Primary: Zustand (per AGENTS.md guidelines)

**Installation:**
```bash
npm install zustand
```

**Why Zustand:**
- **Already recommended** in your AGENTS.md
- **Minimal boilerplate**: No providers, reducers, or actions
- **TypeScript-friendly**: Great type inference
- **Devtools support**: Works with Redux DevTools
- **Small bundle**: ~1KB gzipped

**Controls Store Implementation:**
```typescript
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface ControlsState {
  // Global state
  asOf: AsOfSpec;
  resolvedAsOf: string | null;
  filters: FilterSpec;

  // UI state
  selectedControlIds: string[];
  drawerControlId: string | null;

  // Actions
  setAsOf: (spec: AsOfSpec) => void;
  setResolvedAsOf: (resolved: string) => void;
  setFilters: (filters: Partial<FilterSpec>) => void;
  resetFilters: () => void;
  selectControl: (id: string) => void;
  deselectControl: (id: string) => void;
  openDrawer: (id: string) => void;
  closeDrawer: () => void;
}

const defaultFilters: FilterSpec = {
  control_status: ['Active'],
  hierarchy_level: [],
  risk_theme_ids: [],
  // ... other defaults
};

export const useControlsStore = create<ControlsState>()(
  devtools(
    persist(
      (set) => ({
        asOf: { mode: 'CURRENT', date: null, timezone: 'UTC' },
        resolvedAsOf: null,
        filters: defaultFilters,
        selectedControlIds: [],
        drawerControlId: null,

        setAsOf: (spec) => set({ asOf: spec }),
        setResolvedAsOf: (resolved) => set({ resolvedAsOf: resolved }),
        setFilters: (newFilters) => set((state) => ({
          filters: { ...state.filters, ...newFilters }
        })),
        resetFilters: () => set({ filters: defaultFilters }),
        selectControl: (id) => set((state) => ({
          selectedControlIds: [...state.selectedControlIds, id]
        })),
        deselectControl: (id) => set((state) => ({
          selectedControlIds: state.selectedControlIds.filter(cid => cid !== id)
        })),
        openDrawer: (id) => set({ drawerControlId: id }),
        closeDrawer: () => set({ drawerControlId: null }),
      }),
      { name: 'controls-store' } // localStorage key
    )
  )
);
```

**References:**
- [Zustand GitHub](https://github.com/pmndrs/zustand)
- [Zustand Documentation](https://docs.pmnd.rs/zustand/getting-started/introduction)

---

### 2.5 Data Fetching

#### Primary: TanStack Query (React Query)

**Installation:**
```bash
npm install @tanstack/react-query
```

**Why TanStack Query:**
- **Caching**: Automatic caching with configurable stale times
- **Background Refetch**: Keeps data fresh without blocking UI
- **Pagination**: Built-in infinite scroll support
- **Optimistic Updates**: Great for interactive dashboards
- **DevTools**: Excellent debugging experience

**Usage Pattern:**
```typescript
import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { controlsApi } from '@/services/controls/api';

// Simple query
function useControlDetails(controlId: string) {
  return useQuery({
    queryKey: ['control', controlId],
    queryFn: () => controlsApi.get(controlId),
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: !!controlId,
  });
}

// List with filters (refetches when filters change)
function useControlsList(filters: FilterSpec, page: PageSpec) {
  const { asOf } = useControlsStore();

  return useQuery({
    queryKey: ['controls', 'list', filters, page, asOf],
    queryFn: () => controlsApi.list({ filters, page, as_of: asOf }),
    staleTime: 2 * 60 * 1000,
    keepPreviousData: true, // Smooth pagination
  });
}

// Infinite scroll
function useControlsInfinite(filters: FilterSpec) {
  return useInfiniteQuery({
    queryKey: ['controls', 'infinite', filters],
    queryFn: ({ pageParam = 0 }) =>
      controlsApi.list({ filters, page: { offset: pageParam, limit: 50 } }),
    getNextPageParam: (lastPage, pages) =>
      lastPage.rows.length === 50 ? pages.length * 50 : undefined,
  });
}
```

**References:**
- [TanStack Query Docs](https://tanstack.com/query/latest)

---

### 2.6 UI Components & Utilities

| Category | Library | Purpose | Installation |
|----------|---------|---------|--------------|
| **Icons** | lucide-react | Already in project | `npm install lucide-react` |
| **Icons** | @phosphor-icons/react | Alternative with more variants | `npm install @phosphor-icons/react` |
| **Tooltips** | @radix-ui/react-tooltip | Accessible tooltips | `npm install @radix-ui/react-tooltip` |
| **Popover** | @radix-ui/react-popover | Filter dropdowns, date picker | `npm install @radix-ui/react-popover` |
| **Dialog** | @radix-ui/react-dialog | Modals (compare, diff viewer) | `npm install @radix-ui/react-dialog` |
| **Tabs** | @radix-ui/react-tabs | Control details tabs | `npm install @radix-ui/react-tabs` |
| **Accordion** | @radix-ui/react-accordion | Filter rail sections | `npm install @radix-ui/react-accordion` |
| **Select** | @radix-ui/react-select | Styled dropdowns | `npm install @radix-ui/react-select` |
| **Checkbox** | @radix-ui/react-checkbox | Row selection | `npm install @radix-ui/react-checkbox` |
| **Toast** | sonner | Notifications | `npm install sonner` |
| **Diff Viewer** | react-diff-viewer-continued | History diff view | `npm install react-diff-viewer-continued` |
| **Keyboard** | @react-hook/keyboard | Keyboard shortcuts | `npm install @react-hook/keyboard` |

**Why Radix UI:**
- **Headless**: Works perfectly with Tailwind (no style conflicts)
- **Accessible**: WAI-ARIA compliant out of the box
- **Composable**: Use only what you need
- **Shadcn Foundation**: If you add Shadcn later, it's built on Radix

---

### 2.7 Export & File Generation

| Category | Library | Purpose | Installation |
|----------|---------|---------|--------------|
| **CSV Export** | papaparse | CSV generation & parsing | `npm install papaparse` |
| **Excel Export** | xlsx | Excel file generation | `npm install xlsx` |
| **PDF Export** | @react-pdf/renderer | PDF report generation | `npm install @react-pdf/renderer` |

---

### 2.8 Complete Package.json Additions

```json
{
  "dependencies": {
    // Charting
    "echarts": "^5.5.0",
    "echarts-for-react": "^3.0.2",

    // Data Grid & Virtualization
    "@tanstack/react-table": "^8.11.0",
    "@tanstack/react-virtual": "^3.0.0",

    // Data Fetching
    "@tanstack/react-query": "^5.17.0",

    // State Management
    "zustand": "^4.4.0",

    // Date Handling
    "react-day-picker": "^8.10.0",
    "date-fns": "^3.2.0",

    // UI Primitives (Radix)
    "@radix-ui/react-accordion": "^1.1.2",
    "@radix-ui/react-checkbox": "^1.0.4",
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-popover": "^1.0.7",
    "@radix-ui/react-select": "^2.0.0",
    "@radix-ui/react-tabs": "^1.0.4",
    "@radix-ui/react-tooltip": "^1.0.7",

    // Utilities
    "sonner": "^1.3.0",
    "react-diff-viewer-continued": "^3.3.0",
    "papaparse": "^5.4.0"
  }
}
```

---

### 2.9 Library Decision Summary

| Use Case | Recommended Library | Alternative |
|----------|-------------------|-------------|
| **Charts/Heatmaps** | ECharts + echarts-for-react | Recharts (simpler but less powerful) |
| **Data Grid** | TanStack Table + TanStack Virtual | AG Grid (if budget allows) |
| **Date Picker** | react-day-picker | react-datepicker |
| **State Management** | Zustand | Jotai (more atomic) |
| **Data Fetching** | TanStack Query | SWR (simpler) |
| **UI Primitives** | Radix UI | Headless UI |
| **Notifications** | Sonner | react-hot-toast |

---

## 3. Architecture Overview

### 2.1 Frontend Architecture

```
client/src/
├── pages/
│   └── Controls/                    # NEW: Controls Command Center
│       ├── index.tsx                # Route exports
│       ├── ControlsLayout.tsx       # Shared layout with sidebar + header
│       ├── Overview/                # Portfolio Overview (landing)
│       ├── Explorer/                # Controls Explorer (data grid)
│       ├── Quality/                 # Documentation Quality
│       ├── Similarity/              # Similar Controls & Rationalization
│       ├── History/                 # History & Change Intelligence
│       ├── Details/                 # Control Details (single control)
│       └── components/              # Shared components
│           ├── AsOfDatePicker.tsx
│           ├── FilterRail.tsx
│           ├── GlobalSearchBar.tsx
│           ├── ControlsDataGrid.tsx
│           ├── ChartCard.tsx
│           ├── HeatmapChart.tsx
│           ├── ControlDrawer.tsx
│           └── GuidelineCoach.tsx
├── hooks/
│   └── controls/                    # NEW: Controls-specific hooks
│       ├── useControlsFilters.ts
│       ├── useAsOfDate.ts
│       ├── useControlsSearch.ts
│       └── useControlsAnalytics.ts
├── services/
│   └── controls/                    # NEW: API service layer
│       ├── api.ts                   # API client
│       ├── types.ts                 # TypeScript interfaces
│       └── mockData.ts              # Mock data for Phase 1
└── context/
    └── ControlsContext.tsx          # NEW: Controls state management
```

### 2.2 Backend Architecture (MCP-Ready)

```
server/pipelines/controls/
├── api/
│   └── controls_api.py              # NEW: Controls Command Center endpoints
├── consumer/
│   ├── service.py                   # Existing: Graph traversal queries
│   ├── analytics.py                 # NEW: Aggregation & KPI calculations
│   ├── search.py                    # NEW: FTS + Semantic + Hybrid search
│   └── snapshot.py                  # NEW: As-of-date snapshot resolver
└── mcp/
    └── tools.py                     # NEW: MCP tool definitions
```

### 3.3 MCP Tool Design Principles

Based on Anthropic's guidance for writing agent-friendly tools:

1. **Consolidate Functionality**: Single tools for multi-step operations
2. **Semantic Identifiers**: Use `control_title` not just `control_id` in responses
3. **Flexible Response Formats**: Support `concise` and `detailed` modes
4. **Token Efficiency**: Pagination, filtering, sensible defaults
5. **Actionable Error Messages**: Clear guidance on how to fix errors
6. **Clear Naming**: Unambiguous parameter names with prefixes

---

## 4. Controls Layout Shell - Deep Dive

This section explains how the `ControlsLayout` component works as a shell that wraps all Controls pages, providing consistent navigation, global controls (As-Of date, Search), and shared state.

### 4.1 The Layout Pattern Explained

The Controls Command Center uses **React Router's nested routes** pattern. The `ControlsLayout` acts as a **wrapper/shell** that:
1. Renders persistent UI elements (header, sidebar, global search)
2. Uses React Router's `<Outlet />` to render child pages
3. Provides shared context/state to all child pages

```
URL: /controls/explorer

┌─────────────────────────────────────────────────────────────────┐
│                      ControlsLayout.tsx                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ HEADER BAR (always visible)                               │  │
│  │ [Logo] Controls Command Center  [GlobalSearchBar] [AsOf]  │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌──────────┬────────────────────────────────────────────────┐  │
│  │ SIDEBAR  │                                                │  │
│  │          │   <Outlet />  ← React Router renders           │  │
│  │ Overview │              ControlsExplorer.tsx here         │  │
│  │ Explorer │                                                │  │
│  │ Quality  │   ┌────────────────────────────────────────┐   │  │
│  │ Similar  │   │  ControlsExplorer Component            │   │  │
│  │ History  │   │  (receives filters, asOf from store)   │   │  │
│  │          │   │                                        │   │  │
│  │ ──────── │   │  Uses: useControlsStore()              │   │  │
│  │ Saved    │   │  Uses: useControlsList() hook          │   │  │
│  │ Views    │   │                                        │   │  │
│  │          │   └────────────────────────────────────────┘   │  │
│  └──────────┴────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Route Configuration

**File: `client/src/config/routes.tsx`**

```typescript
import { ControlsLayout } from '@/pages/Controls/ControlsLayout';
import { ControlsOverview } from '@/pages/Controls/Overview/ControlsOverview';
import { ControlsExplorer } from '@/pages/Controls/Explorer/ControlsExplorer';
import { ControlsQuality } from '@/pages/Controls/Quality/ControlsQuality';
import { ControlsSimilarity } from '@/pages/Controls/Similarity/ControlsSimilarity';
import { ControlsHistory } from '@/pages/Controls/History/ControlsHistory';
import { ControlDetails } from '@/pages/Controls/Details/ControlDetails';

export const routes = [
  // ... other routes
  {
    path: "/controls",
    element: <ControlsLayout />,  // Parent layout component
    protected: true,
    accessRight: "hasDashboardAccess",
    children: [
      // These render inside ControlsLayout's <Outlet />
      { index: true, element: <ControlsOverview /> },           // /controls
      { path: "explorer", element: <ControlsExplorer /> },      // /controls/explorer
      { path: "quality", element: <ControlsQuality /> },        // /controls/quality
      { path: "similarity", element: <ControlsSimilarity /> },  // /controls/similarity
      { path: "history", element: <ControlsHistory /> },        // /controls/history
      { path: ":controlId", element: <ControlDetails /> },      // /controls/CTRL-001
    ],
  },
];
```

### 6.3 ControlsLayout Implementation

**File: `client/src/pages/Controls/ControlsLayout.tsx`**

```typescript
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useControlsStore } from '@/store/controlsStore';
import { AsOfDatePicker } from './components/AsOfDatePicker';
import { GlobalSearchBar } from './components/GlobalSearchBar';
import { ControlsSidebar } from './components/ControlsSidebar';
import { ControlDrawer } from './components/ControlDrawer';

export function ControlsLayout() {
  const location = useLocation();
  const { asOf, setAsOf, resolvedAsOf, drawerControlId, closeDrawer } = useControlsStore();

  // Determine current page for breadcrumb
  const currentPage = getPageName(location.pathname);

  return (
    <div className="min-h-screen bg-surface-light flex flex-col">
      {/* ════════════════════════════════════════════════════════════
          HEADER BAR - Always visible on all /controls/* pages
          ════════════════════════════════════════════════════════════ */}
      <header className="sticky top-0 z-40 bg-white border-b border-border-light">
        <div className="h-12 px-4 flex items-center justify-between">
          {/* Left: Logo & Title */}
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary">shield</span>
            <h1 className="text-sm font-bold text-text-main">
              Controls Command Center
            </h1>
          </div>

          {/* Center: Global Search */}
          <div className="flex-1 max-w-2xl mx-8">
            <GlobalSearchBar />
          </div>

          {/* Right: As-Of Date & User */}
          <div className="flex items-center gap-4">
            <AsOfDatePicker
              value={asOf}
              onChange={setAsOf}
              resolvedTo={resolvedAsOf}
            />
            {/* User menu would go here */}
          </div>
        </div>
      </header>

      {/* ════════════════════════════════════════════════════════════
          MAIN CONTENT AREA - Sidebar + Page Content
          ════════════════════════════════════════════════════════════ */}
      <div className="flex flex-1 overflow-hidden">
        {/* ─────────────────────────────────────────────────────────
            SIDEBAR - Navigation between Controls pages
            ───────────────────────────────────────────────────────── */}
        <aside className="w-48 flex-shrink-0 bg-white border-r border-border-light">
          <ControlsSidebar />
        </aside>

        {/* ─────────────────────────────────────────────────────────
            CONTENT AREA - Child routes render here via <Outlet />
            ───────────────────────────────────────────────────────── */}
        <main className="flex-1 overflow-auto">
          {/* Breadcrumb */}
          <div className="px-6 py-3 border-b border-border-light bg-white">
            <nav className="text-xs text-text-sub">
              <span>Controls</span>
              {currentPage && (
                <>
                  <span className="mx-2">/</span>
                  <span className="text-text-main font-medium">{currentPage}</span>
                </>
              )}
            </nav>
          </div>

          {/* ══════════════════════════════════════════════════════
              THIS IS WHERE CHILD PAGES RENDER

              When URL is /controls/explorer:
                → <ControlsExplorer /> renders here

              When URL is /controls/quality:
                → <ControlsQuality /> renders here

              When URL is /controls/CTRL-001:
                → <ControlDetails /> renders here
              ══════════════════════════════════════════════════════ */}
          <div className="p-6">
            <Outlet />
          </div>
        </main>
      </div>

      {/* ════════════════════════════════════════════════════════════
          CONTROL DRAWER - Slide-over panel for quick preview
          Shows when user clicks a control row in any page
          ════════════════════════════════════════════════════════════ */}
      <ControlDrawer
        controlId={drawerControlId}
        onClose={closeDrawer}
      />
    </div>
  );
}

function getPageName(pathname: string): string | null {
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length <= 1) return 'Overview';
  const page = segments[1];
  const pageNames: Record<string, string> = {
    explorer: 'Explorer',
    quality: 'Documentation Quality',
    similarity: 'Similar Controls',
    history: 'History & Changes',
  };
  return pageNames[page] || 'Control Details';
}
```

### 6.4 How Data Flows

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ZUSTAND STORE                                    │
│  useControlsStore()                                                     │
│  ├── asOf: { mode, date, timezone }                                    │
│  ├── resolvedAsOf: "2026-02-01T00:00:00Z"                              │
│  ├── filters: { control_status, risk_themes, ... }                     │
│  ├── selectedControlIds: []                                            │
│  └── drawerControlId: null | "CTRL-001"                                │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             │ All components read/write to same store
                             │
    ┌────────────────────────┼────────────────────────────────────────────┐
    │                        │                                            │
    ▼                        ▼                                            ▼
┌─────────────┐    ┌─────────────────────┐                    ┌──────────────────┐
│ AsOfDate    │    │ ControlsExplorer    │                    │ FilterRail       │
│ Picker      │    │ (child page)        │                    │ (in Explorer)    │
│             │    │                     │                    │                  │
│ Reads: asOf │    │ Reads: filters, asOf│                    │ Reads: filters   │
│ Writes: set │    │ Uses: useControls   │                    │ Writes: setFilter│
│       AsOf  │    │       List() hook   │                    │                  │
└─────────────┘    └─────────────────────┘                    └──────────────────┘
                             │
                             │ Query with current filters + asOf
                             ▼
                   ┌─────────────────────┐
                   │ TanStack Query      │
                   │ useControlsList()   │
                   │                     │
                   │ queryKey: [         │
                   │   'controls',       │
                   │   filters,          │
                   │   asOf              │
                   │ ]                   │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ API Call            │
                   │ POST /api/controls/ │
                   │      list           │
                   └─────────────────────┘
```

### 4.5 Navigation & State Persistence

**Sidebar Navigation:**

When user clicks "Explorer" in sidebar:
1. React Router navigates to `/controls/explorer`
2. `ControlsLayout` stays mounted (no re-render of header/sidebar)
3. Only the `<Outlet />` content changes to `<ControlsExplorer />`
4. Filters and asOf state **persist** because they're in Zustand store

**Opening Control Details:**

When user clicks a control row in Explorer:
1. Two options:
   - **Quick Preview**: Opens `ControlDrawer` (slide-over panel)
   - **Full Details**: Navigates to `/controls/CTRL-001`
2. If navigating to full details, the layout stays but `<Outlet />` renders `<ControlDetails />`

### 4.6 Page-Specific Components

Each child page may have its own layout additions:

```
/controls (Overview)
├── ControlsLayout (shell)
└── <Outlet /> → ControlsOverview
    ├── KPIRow (6 cards)
    ├── HeatmapRow (2 heatmaps)
    ├── DistributionsRow (3 bar charts)
    └── ExceptionsTable

/controls/explorer
├── ControlsLayout (shell)
└── <Outlet /> → ControlsExplorer
    ├── Toolbar (search, columns, export)
    ├── FilterRail (left sidebar - INSIDE the page, not in layout)
    └── DataGrid

/controls/CTRL-001
├── ControlsLayout (shell)
└── <Outlet /> → ControlDetails
    ├── Header (badges, back button)
    ├── TabsNav (Summary, Relationships, History, Similar)
    ├── TabContent
    └── GuidelineCoach (right panel)
```

### 4.7 FilterRail Position Clarification

**Important**: The `FilterRail` is **NOT** part of `ControlsLayout`. It's a component used **inside** specific pages that need filtering (Explorer, Quality, etc.).

```
ControlsLayout
├── Header (global)
├── Sidebar (navigation links - global)
└── <Outlet />
    └── ControlsExplorer
        ├── FilterRail (page-specific - left side)
        └── DataGrid (page-specific - right side)
```

This allows different pages to have different filter configurations or no filters at all (like the Overview page which shows aggregated data).

### 4.8 Complete File Structure with Layout Relationship

```
client/src/pages/Controls/
├── index.tsx                    # Barrel export
├── ControlsLayout.tsx           # 🔴 THE SHELL (wraps all pages)
│
├── components/                  # Shared components used across pages
│   ├── AsOfDatePicker.tsx       # Used in ControlsLayout header
│   ├── GlobalSearchBar.tsx      # Used in ControlsLayout header
│   ├── ControlsSidebar.tsx      # Used in ControlsLayout sidebar
│   ├── ControlDrawer.tsx        # Used in ControlsLayout (overlay)
│   ├── FilterRail.tsx           # Used INSIDE Explorer, Quality pages
│   ├── ControlsDataGrid.tsx     # Used INSIDE Explorer page
│   ├── ChartCard.tsx            # Used INSIDE Overview, Quality pages
│   ├── HeatmapChart.tsx         # Used INSIDE Overview, Quality pages
│   ├── GuidelineCoach.tsx       # Used INSIDE Details page
│   └── DiffViewer.tsx           # Used INSIDE History page
│
├── Overview/                    # 🔵 Child page (renders in Outlet)
│   └── ControlsOverview.tsx
│
├── Explorer/                    # 🔵 Child page (renders in Outlet)
│   └── ControlsExplorer.tsx     # Contains FilterRail + DataGrid
│
├── Quality/                     # 🔵 Child page (renders in Outlet)
│   └── ControlsQuality.tsx      # Contains FilterRail + Heatmap
│
├── Similarity/                  # 🔵 Child page (renders in Outlet)
│   └── ControlsSimilarity.tsx
│
├── History/                     # 🔵 Child page (renders in Outlet)
│   └── ControlsHistory.tsx      # Contains DiffViewer
│
└── Details/                     # 🔵 Child page (renders in Outlet)
    └── ControlDetails.tsx       # Contains Tabs + GuidelineCoach
```

### 4.9 Visual Flow Diagram

```
User visits /controls/explorer
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ App.tsx                                                         │
│ ├── <Routes>                                                    │
│ │   ├── <Route path="/controls" element={<ControlsLayout />}>  │
│ │   │   ├── <Route index element={<ControlsOverview />} />     │
│ │   │   ├── <Route path="explorer" element={<ControlsExplorer />} /> ← MATCH!
│ │   │   └── ...                                                 │
│ │   └── ...                                                     │
└─────────────────────────────────────────────────────────────────┘
         │
         │ React Router renders:
         │ 1. ControlsLayout (parent)
         │ 2. ControlsExplorer (inside Outlet)
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ ControlsLayout renders:                                         │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ <header>...</header>                                        │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │ <aside><ControlsSidebar /></aside>                          │ │
│ │ <main>                                                      │ │
│ │   <Outlet /> ← ControlsExplorer renders here                │ │
│ │ </main>                                                     │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ ControlsExplorer renders (inside Outlet):                       │
│ ┌──────────┬──────────────────────────────────────────────────┐ │
│ │ Filter   │ <ControlsDataGrid data={...} />                  │ │
│ │ Rail     │                                                  │ │
│ │          │                                                  │ │
│ └──────────┴──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Phase 1: UI Implementation with Mock Data

### 9.1 Phase 1 Timeline & Milestones

```
Phase 1.1: Foundation (Week 1-2)
├── Setup routing & layout structure
├── Implement shared components (AsOfDatePicker, FilterRail, SearchBar)
├── Create mock data generators
└── Build ControlsContext for state management

Phase 1.2: Core Pages (Week 3-4)
├── Portfolio Overview page with KPI cards & charts
├── Controls Explorer with DataGrid
├── Control Details page (single control view)
└── Guideline Coach panel

Phase 1.3: Advanced Pages (Week 5-6)
├── Documentation Quality page
├── Similar Controls & Rationalization
├── History & Change Intelligence
└── Role-based dashboard variants
```

### 9.2 Step-by-Step Implementation

#### Step 1: Project Setup & Routing

**File: `client/src/config/routes.tsx`**
Add new routes:

```typescript
// Add to existing routes array
{
  path: "/controls",
  component: ControlsLayout,
  name: "Controls",
  protected: true,
  accessRight: "hasDashboardAccess",
  children: [
    { path: "", component: ControlsOverview, name: "Overview" },
    { path: "explorer", component: ControlsExplorer, name: "Explorer" },
    { path: "quality", component: ControlsQuality, name: "Quality" },
    { path: "similarity", component: ControlsSimilarity, name: "Similarity" },
    { path: "history", component: ControlsHistory, name: "History" },
    { path: ":controlId", component: ControlDetails, name: "Details" },
  ]
}
```

#### Step 2: Controls Layout Shell

**File: `client/src/pages/Controls/ControlsLayout.tsx`**

```
┌─────────────────────────────────────────────────────────────────┐
│ TOP BAR                                                         │
│ [Logo] Controls Command Center    [Search Bar]    [As-Of] [User]│
├──────────┬──────────────────────────────────────────────────────┤
│ SIDEBAR  │ MAIN CONTENT                                         │
│          │                                                      │
│ Overview │ ┌──────────────────────────────────────────────────┐ │
│ Explorer │ │ Page Header + Breadcrumb                         │ │
│ Quality  │ ├──────────────────────────────────────────────────┤ │
│ Similar  │ │                                                  │ │
│ History  │ │ Content Area (routes render here)                │ │
│          │ │                                                  │ │
│ ──────── │ │                                                  │ │
│ Saved    │ │                                                  │ │
│ Views    │ │                                                  │ │
│          │ └──────────────────────────────────────────────────┘ │
└──────────┴──────────────────────────────────────────────────────┘
```

#### Step 3: Shared Components

**3.1 AsOfDatePicker Component**

Purpose: Global snapshot date selector with resolution display

```typescript
interface AsOfDatePickerProps {
  value: AsOfSpec;
  onChange: (spec: AsOfSpec) => void;
  resolvedTo?: string;  // Server returns actual resolved timestamp
}

interface AsOfSpec {
  mode: 'CURRENT' | 'DATE';
  date: string | null;  // YYYY-MM-DD when mode=DATE
  timezone: string;
}
```

UI Elements:
- Toggle: "Current" | "Historical"
- Date picker (when Historical selected)
- Chip showing "Resolved to: 2026-02-01T00:00:00Z"

**3.2 FilterRail Component**

Purpose: Left sidebar with collapsible filter sections

```typescript
interface FilterRailProps {
  filters: FilterSpec;
  onChange: (filters: FilterSpec) => void;
  onReset: () => void;
  onSaveView?: (name: string) => void;
}

interface FilterSpec {
  // Scope
  owning_function_ids: string[];
  owning_location_ids: string[];
  hierarchy_level: ('Level 1' | 'Level 2')[];
  control_status: string[];

  // Risk & Taxonomy
  risk_theme_ids: string[];
  sox_relevant: boolean | null;
  ccar_relevant: boolean | null;
  bcbs239_relevant: boolean | null;

  // Control Design
  preventative_detective: string[];
  manual_automated: string[];
  execution_frequency: string[];

  // Ownership
  owner_gpn: string[];
  delegate_gpn: string[];
  assessor_gpn: string[];

  // Quality Flags
  missing_evidence: boolean | null;
  missing_why: boolean | null;
  has_abbreviations: boolean | null;
  stale_days: number | null;
}
```

Filter Sections (Accordion):
1. **Scope** - Function/Location hierarchy, Level, Status
2. **Risk & Taxonomy** - Risk themes, AI taxonomy, Regulatory flags
3. **Control Design** - Prevent/Detect, Manual/Auto, Frequency
4. **Ownership** - Owner/Delegate/Assessor GPNs
5. **Data Quality** - Missing fields, Abbreviations, Staleness

**3.3 GlobalSearchBar Component**

Purpose: Unified search with mode tabs

```typescript
interface GlobalSearchBarProps {
  onSearch: (query: SearchQuery) => void;
  placeholder?: string;
}

interface SearchQuery {
  text: string;
  mode: 'KEYWORD' | 'SEMANTIC' | 'HYBRID';
  fields: string[];  // Which fields to search
}
```

UI Elements:
- Search input with icon
- Mode tabs: Keyword | Semantic | Hybrid
- Field selector dropdown (Title, Description, Evidence, etc.)
- "Explain results" toggle

**3.4 ControlsDataGrid Component**

Purpose: Reusable data grid for controls list

```typescript
interface ControlsDataGridProps {
  data: ControlRow[];
  columns: ColumnDef[];
  loading: boolean;
  onRowClick: (control: ControlRow) => void;
  onCompare?: (controls: ControlRow[]) => void;
  groupBy?: string;
  sortBy?: SortSpec[];
}
```

Features:
- Column chooser
- Group by (risk_theme, owner, function, etc.)
- Multi-sort
- Row expansion for quick preview
- Checkbox selection for compare
- Pagination

**3.5 ChartCard Component**

Purpose: Wrapper for charts with standard header

```typescript
interface ChartCardProps {
  title: string;
  subtitle?: string;
  resolvedAsOf?: string;
  children: React.ReactNode;
  onDrilldown?: (filterPatch: Partial<FilterSpec>) => void;
}
```

**3.6 HeatmapChart Component**

Purpose: Risk theme × Function/Location heatmap

```typescript
interface HeatmapChartProps {
  data: HeatmapCell[];
  xAxis: { field: string; label: string };
  yAxis: { field: string; label: string };
  metric: 'COUNT' | 'PCT_INCOMPLETE' | 'PCT_MISSING_EVIDENCE';
  colorScale: 'sequential' | 'diverging';
  onCellClick: (cell: HeatmapCell) => void;
}
```

**3.7 ControlDrawer Component**

Purpose: Slide-over panel for quick control preview

```typescript
interface ControlDrawerProps {
  controlId: string | null;
  onClose: () => void;
  onOpenDetails: (controlId: string) => void;
}
```

Content:
- Summary header with badges
- Quick quality checklist
- Similar controls preview (top 3)
- "Open full details" button

**3.8 GuidelineCoach Component**

Purpose: Contextual help panel showing documentation guidance

```typescript
interface GuidelineCoachProps {
  control?: ControlRecord;  // Show control-specific checklist
  field?: string;           // Show field-specific guidance
}
```

Content:
- Missing field checklist
- Field definitions with "why it matters"
- Good vs bad examples
- Abbreviations found

#### Step 4: Page Implementations

**4.1 Portfolio Overview Page (`/controls`)**

```
┌────────────────────────────────────────────────────────────────┐
│ KPI ROW (6 cards)                                              │
│ [Total] [Doc %] [Evidence %] [Stale %] [Conflicts] [Duplicates]│
├────────────────────────────────────────────────────────────────┤
│ HEATMAP ROW                                                    │
│ ┌─────────────────────┐ ┌─────────────────────┐               │
│ │ Risk Theme ×        │ │ Risk Theme ×        │               │
│ │ Owning Function     │ │ Owning Location     │               │
│ └─────────────────────┘ └─────────────────────┘               │
├────────────────────────────────────────────────────────────────┤
│ DISTRIBUTIONS ROW                                              │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│ │ Manual/Auto  │ │ Prevent/Det  │ │ Frequency    │            │
│ │ by Risk Theme│ │ by Risk Theme│ │ Distribution │            │
│ └──────────────┘ └──────────────┘ └──────────────┘            │
├────────────────────────────────────────────────────────────────┤
│ EXCEPTIONS TABLE                                               │
│ "Needs Attention" list with quick actions                      │
└────────────────────────────────────────────────────────────────┘
```

**4.2 Controls Explorer Page (`/controls/explorer`)**

```
┌──────────┬─────────────────────────────────────────────────────┐
│ FILTER   │ TOOLBAR                                             │
│ RAIL     │ [Search] [Columns] [Group By] [Compare] [Export]    │
│          ├─────────────────────────────────────────────────────┤
│ Scope    │ DATA GRID                                           │
│ Risk     │ ┌─────┬────────┬───────┬─────┬──────┬─────┬───────┐│
│ Design   │ │ ID  │ Title  │ Level │Owner│Theme │Freq │Quality││
│ Owner    │ ├─────┼────────┼───────┼─────┼──────┼─────┼───────┤│
│ Quality  │ │ ... │ ...    │ ...   │ ... │ ...  │ ... │ ...   ││
│          │ │ ... │ ...    │ ...   │ ... │ ...  │ ... │ ...   ││
│          │ └─────┴────────┴───────┴─────┴──────┴─────┴───────┘│
│          │                                                     │
│ [Reset]  │ PAGINATION [1] [2] [3] ... [50]  Showing 1-50 of N │
│ [Save]   │                                                     │
└──────────┴─────────────────────────────────────────────────────┘
```

**4.3 Control Details Page (`/controls/:controlId`)**

```
┌────────────────────────────────────────────────────────────────┐
│ HEADER                                                         │
│ [< Back] CTRL-0000001234 | Daily reconciliation of...          │
│ [Level 2] [Active] [Detective] [IT Dependent] [Daily]          │
├───────────────────────────────────────────────┬────────────────┤
│ TABS                                          │ GUIDELINE      │
│ [Summary] [Relationships] [History] [Similar] │ COACH          │
├───────────────────────────────────────────────┤                │
│                                               │ Checklist:     │
│ TAB CONTENT                                   │ ✓ What         │
│                                               │ ✓ Who          │
│ Summary Tab:                                  │ ✗ Why          │
│ - Owning function/location cards              │ ✓ When         │
│ - Classification badges                       │ ✓ Where        │
│ - Evidence readiness                          │ ✗ Escalation   │
│ - Regulatory badges (SOX/CCAR/BCBS239)        │                │
│                                               │ Abbreviations: │
│                                               │ KPCi, ERMS     │
│                                               │                │
└───────────────────────────────────────────────┴────────────────┘
```

**4.4 Documentation Quality Page (`/controls/quality`)**

```
┌────────────────────────────────────────────────────────────────┐
│ KPI ROW (completeness by category)                             │
│ [What %] [Who %] [When %] [Where %] [Why %] [Evidence %]       │
├────────────────────────────────────────────────────────────────┤
│ COMPLETENESS MATRIX HEATMAP                                    │
│ Rows: Functions/Locations                                      │
│ Cols: what | who | when | where | why | evidence | escalation  │
│ Cell: % "Yes"                                                  │
├────────────────────────────────────────────────────────────────┤
│ TABS: [Missing Evidence] [Missing Escalation] [Abbreviations]  │
│ ┌──────────────────────────────────────────────────────────┐  │
│ │ Top Offenders List                                        │  │
│ │ - Control A: Missing why, escalation                      │  │
│ │ - Control B: Missing evidence                             │  │
│ └──────────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────────┤
│ TREND CHART                                                    │
│ Completeness over time (using version tables)                  │
└────────────────────────────────────────────────────────────────┘
```

**4.5 Similar Controls Page (`/controls/similarity`)**

```
┌──────────────┬───────────────────────┬─────────────────────────┐
│ SEED CONTROL │ SIMILAR RESULTS       │ EXPLANATION PANEL       │
│              │                       │                         │
│ Search:      │ Ranked List:          │ Similarity Breakdown:   │
│ [________]   │ 1. CTRL-002 (0.92)    │ - Title: 0.85           │
│              │ 2. CTRL-045 (0.88)    │ - Description: 0.91     │
│ Selected:    │ 3. CTRL-123 (0.85)    │ - Evidence: 0.78        │
│ CTRL-001     │ 4. CTRL-067 (0.82)    │                         │
│ Daily rec... │ 5. CTRL-089 (0.79)    │ FTS Overlaps:           │
│              │                       │ "reconciliation"        │
│ ──────────── │ ──────────────        │ "daily"                 │
│ Basis:       │                       │ "evidence"              │
│ [Combined ▼] │ [Compare Selected]    │                         │
│              │ [Create Candidate Set]│ Metadata Mismatches:    │
│ Threshold:   │                       │ - Frequency: Daily vs   │
│ [====●===]   │                       │   Monthly               │
│ 0.75         │                       │ - Risk Theme: Same      │
└──────────────┴───────────────────────┴─────────────────────────┘
```

**4.6 History & Change Intelligence Page (`/controls/history`)**

```
┌────────────────────────────────────────────────────────────────┐
│ DATE RANGE: [From: ______] [To: ______]                        │
├────────────────────────────────────────────────────────────────┤
│ CHANGE SUMMARY TILES                                           │
│ [+42 New] [-5 Deactivated] [~28 Freq Changed] [~15 Type Changed]│
├────────────────────────────────────────────────────────────────┤
│ CHANGE EVENTS TABLE                                            │
│ ┌──────┬────────┬────────────┬─────────────┬──────────────────┐│
│ │ Date │ Control│ Change Type│ From → To   │ Details          ││
│ ├──────┼────────┼────────────┼─────────────┼──────────────────┤│
│ │ 1/15 │CTRL-001│ FREQUENCY  │ Monthly→Daily│ [View Diff]     ││
│ │ 1/14 │CTRL-045│ NEW        │ —           │ [View]           ││
│ │ 1/14 │CTRL-067│ DEACTIVATED│ Active→Inact│ Reason: Merged   ││
│ └──────┴────────┴────────────┴─────────────┴──────────────────┘│
├────────────────────────────────────────────────────────────────┤
│ DIFF VIEWER (Modal)                                            │
│ ┌─────────────────────┬─────────────────────┐                  │
│ │ Version A (Before)  │ Version B (After)   │                  │
│ │ Frequency: Monthly  │ Frequency: Daily    │  ← highlighted   │
│ │ Description: ...    │ Description: ...    │                  │
│ └─────────────────────┴─────────────────────┘                  │
└────────────────────────────────────────────────────────────────┘
```

---

## 6. Phase 2: Backend Integration & MCP Tools

### 10.1 Phase 2 Timeline

```
Phase 2.1: Core APIs (Week 7-8)
├── Snapshot resolver service
├── Controls list endpoint with filtering
├── Control details endpoint
└── Basic search (FTS keyword)

Phase 2.2: Analytics APIs (Week 9-10)
├── Overview analytics (KPIs, heatmaps)
├── Quality analytics (completeness metrics)
├── History/changes endpoint
└── Hybrid search (FTS + semantic)

Phase 2.3: MCP Tool Layer (Week 11-12)
├── Tool definitions for agent consumption
├── Response format optimization
├── Error handling refinement
└── Documentation & testing
```

### 10.2 API Endpoint Specifications

#### 10.2.1 `POST /api/controls/list`

**Purpose**: Primary data grid endpoint with filtering, pagination, sorting

**Request**:
```json
{
  "as_of": { "mode": "CURRENT", "date": null, "timezone": "Europe/Warsaw" },
  "filters": {
    "control_status": ["Active"],
    "hierarchy_level": ["Level 2"],
    "risk_theme_ids": ["CYBER_INFOSEC"]
  },
  "group_by": [],
  "sort": [{ "field": "control_id", "dir": "asc" }],
  "page": { "limit": 50, "offset": 0 },
  "include": {
    "ai_enrichment_summary": true,
    "risk_themes": true
  },
  "columns": ["control_id", "control_title", "hierarchy_level", "control_status"]
}
```

**Response**:
```json
{
  "resolved_as_of": {
    "requested": { "mode": "CURRENT" },
    "resolved_to": "2026-02-01T00:00:00Z",
    "resolution_rule": "CURRENT"
  },
  "total": 12842,
  "rows": [
    {
      "control_id": "CTRL-0000001234",
      "control_title": "Daily reconciliation of...",
      "hierarchy_level": "Level 2",
      "control_status": "Active",
      "risk_themes": [{ "risk_theme_id": "CYBER_INFOSEC", "risk_theme_name": "Cyber and Information Security" }],
      "quality": {
        "doc_completeness_score": 0.71,
        "missing": ["why", "escalation"],
        "has_abbreviations": true
      }
    }
  ]
}
```

#### 10.2.2 `POST /api/controls/search`

**Purpose**: Unified search with FTS, semantic, and hybrid modes

**Request**:
```json
{
  "as_of": { "mode": "CURRENT", "timezone": "Europe/Warsaw" },
  "filters": { "control_status": ["Active"] },
  "query": "reconciliation escalation evidence",
  "mode": "HYBRID",
  "search_fields": ["control_title", "control_description", "evidence_description"],
  "fts": { "k": 50 },
  "semantic": {
    "k": 50,
    "embedding_fields": ["control_description_embedding"],
    "weights": { "control_description_embedding": 1.0 }
  },
  "fusion": { "method": "RRF", "rrf_k": 60, "weights": { "fts": 0.4, "semantic": 0.6 } },
  "page": { "limit": 25, "offset": 0 }
}
```

**Response**:
```json
{
  "resolved_as_of": { ... },
  "total": 913,
  "results": [
    {
      "control_id": "CTRL-0000009876",
      "control_title": "Monthly reconciliation of...",
      "score": 0.812,
      "breakdown": { "fts_score": 12.3, "semantic_score": 0.78, "rrf_rank": 3 },
      "highlights": {
        "control_description": "... <em>evidence</em> must be retained ... <em>escalation</em> ..."
      }
    }
  ]
}
```

#### 10.2.3 `GET /api/controls/{control_id}`

**Purpose**: Single control with full details

**Query Parameters**:
- `as_of_date` (optional): YYYY-MM-DD
- `include_history` (optional): boolean
- `include_similar` (optional): boolean, k (number)

**Response**:
```json
{
  "resolved_as_of": { ... },
  "control": {
    "control_id": "CTRL-0000001234",
    "hierarchy_level": "Level 2",
    "parent_control_id": "CTRL-0000000001",
    "status": { "control_status": "Active", "valid_from": "2024-01-01T00:00:00Z" },
    "owning": {
      "function": { "function_id": "N14952", "function_name": "Investment Bank" },
      "location": { "location_id": "2210", "location_name": "Frankfurt" }
    },
    "metadata": { ... },
    "text": { "control_title": "...", "control_description": "...", "evidence_description": "..." }
  },
  "relationships": {
    "risk_themes": [...],
    "related_functions": [...],
    "related_locations": [...],
    "sox_assertions": [...],
    "category_flags": [...]
  },
  "ai": {
    "taxonomy": { "primary": {...}, "secondary": null },
    "enrichment": { "what_yes_no": "Yes", "why_yes_no": "No", ... }
  }
}
```

#### 10.2.4 `POST /api/controls/analytics/overview`

**Purpose**: Portfolio overview KPIs and heatmaps

**Request**:
```json
{
  "as_of": { "mode": "CURRENT", "timezone": "Europe/Warsaw" },
  "filters": { "control_status": ["Active"] },
  "metrics": ["TOTAL", "DOC_COMPLETENESS", "EVIDENCE_READY", "STALE_180D", "MAPPING_CONFLICTS", "DUPLICATE_CANDIDATES"],
  "heatmaps": [
    { "x": "risk_theme", "y": "owning_function", "metric": "COUNT" },
    { "x": "risk_theme", "y": "owning_location", "metric": "PCT_MISSING_EVIDENCE" }
  ]
}
```

**Response**:
```json
{
  "resolved_as_of": { ... },
  "kpis": {
    "total": 12842,
    "doc_completeness_pct": 0.74,
    "evidence_ready_pct": 0.69,
    "stale_180d_pct": 0.21,
    "mapping_conflicts": 318,
    "duplicate_candidates": 912
  },
  "heatmaps": [
    {
      "spec": { "x": "risk_theme", "y": "owning_function", "metric": "COUNT" },
      "cells": [{ "x": "CYBER_INFOSEC", "y": "N14952", "value": 412 }]
    }
  ]
}
```

#### 10.2.5 `POST /api/controls/similar`

**Purpose**: Find similar controls using embeddings

**Request**:
```json
{
  "seed_control_id": "CTRL-0000001234",
  "embedding_fields": ["control_description_embedding", "evidence_description_embedding"],
  "weights": { "control_description_embedding": 0.7, "evidence_description_embedding": 0.3 },
  "threshold": 0.75,
  "k": 20,
  "filters": { "control_status": ["Active"] }
}
```

**Response**:
```json
{
  "seed": { "control_id": "CTRL-0000001234", "control_title": "..." },
  "similar": [
    {
      "control_id": "CTRL-0000009876",
      "control_title": "...",
      "similarity_score": 0.92,
      "breakdown": {
        "control_description_embedding": 0.91,
        "evidence_description_embedding": 0.85
      },
      "metadata_mismatches": ["execution_frequency"]
    }
  ]
}
```

#### 10.2.6 `POST /api/controls/changes`

**Purpose**: Get changes between two dates

**Request**:
```json
{
  "from_date": "2026-01-01",
  "to_date": "2026-02-01",
  "change_types": ["NEW", "DEACTIVATED", "FREQUENCY_CHANGED", "TYPE_CHANGED", "DOC_QUALITY_CHANGED"],
  "filters": {},
  "page": { "limit": 50, "offset": 0 }
}
```

**Response**:
```json
{
  "summary": {
    "new_controls": 42,
    "deactivated_controls": 5,
    "frequency_changes": 28,
    "type_changes": 15,
    "doc_quality_improvements": 89,
    "doc_quality_deteriorations": 12
  },
  "events": [
    {
      "control_id": "CTRL-0000001234",
      "change_type": "FREQUENCY_CHANGED",
      "change_date": "2026-01-15T09:00:00Z",
      "from_value": "Monthly",
      "to_value": "Daily",
      "field": "execution_frequency"
    }
  ]
}
```

### 6.3 MCP Tool Definitions

Based on Anthropic's tool design principles, here are the MCP tool specifications:

#### Tool 1: `controls_search`

```python
@mcp_tool(
    name="controls_search",
    description="""Search for controls using keyword, semantic, or hybrid search.

    Use this tool to:
    - Find controls by keyword (e.g., "reconciliation", "daily", "evidence")
    - Find semantically similar controls to a description
    - Combine keyword and semantic search for best results

    The tool returns control IDs, titles, and relevance scores.
    Use response_format="concise" for quick lookups, "detailed" for full context.
    """,
)
async def controls_search(
    query: str,  # The search query text
    mode: Literal["KEYWORD", "SEMANTIC", "HYBRID"] = "HYBRID",
    search_fields: list[str] = ["control_title", "control_description"],
    filters: dict = {},  # Optional filters like {"control_status": ["Active"]}
    limit: int = 10,
    response_format: Literal["concise", "detailed"] = "concise",
) -> dict:
    """
    Returns:
    - concise: [{control_id, title, score}]
    - detailed: [{control_id, title, score, description, highlights, risk_themes}]
    """
```

#### Tool 2: `controls_get`

```python
@mcp_tool(
    name="controls_get",
    description="""Get details for a specific control by ID.

    Use this tool to:
    - Get full control information including relationships and AI analysis
    - Check documentation completeness (what/who/when/where/why)
    - See risk themes and taxonomy mappings
    - View historical versions using as_of_date

    Returns complete control data including relationships and AI enrichment.
    """,
)
async def controls_get(
    control_id: str,  # The control ID (e.g., "CTRL-0000001234")
    as_of_date: str = None,  # Optional: YYYY-MM-DD for historical snapshot
    include_similar: bool = False,  # Include top 5 similar controls
    response_format: Literal["concise", "detailed"] = "detailed",
) -> dict:
    """
    Returns control with relationships, AI taxonomy, enrichment analysis.
    """
```

#### Tool 3: `controls_list`

```python
@mcp_tool(
    name="controls_list",
    description="""List controls with filtering, pagination, and grouping.

    Use this tool to:
    - Get paginated list of controls matching criteria
    - Filter by risk theme, function, location, status, etc.
    - Group results by any dimension
    - Export data for analysis

    Common filters:
    - control_status: ["Active", "Inactive"]
    - hierarchy_level: ["Level 1", "Level 2"]
    - risk_theme_ids: ["CYBER_INFOSEC", "TECH_PROD_STAB"]
    - preventative_detective: ["Preventative", "Detective"]
    - manual_automated: ["Manual", "Automated", "IT dependent automated"]

    Use limit/offset for pagination. Default limit is 50, max is 500.
    """,
)
async def controls_list(
    filters: dict = {},
    sort: list[dict] = [{"field": "control_id", "dir": "asc"}],
    group_by: str = None,  # Optional: "risk_theme", "owning_function", etc.
    limit: int = 50,
    offset: int = 0,
    response_format: Literal["concise", "detailed"] = "concise",
) -> dict:
    """
    Returns paginated list with total count.
    """
```

#### Tool 4: `controls_analytics`

```python
@mcp_tool(
    name="controls_analytics",
    description="""Get portfolio analytics, KPIs, and aggregated metrics.

    Use this tool to:
    - Get portfolio health KPIs (total, completeness %, evidence %, staleness)
    - Generate heatmaps (risk theme × function, risk theme × location)
    - Identify anomalies and exceptions
    - Track trends over time

    Available metrics:
    - TOTAL: Total active controls
    - DOC_COMPLETENESS: % with complete what/who/when/where/why
    - EVIDENCE_READY: % with evidence description + availability
    - STALE_180D: % not modified in 180 days
    - MAPPING_CONFLICTS: Count of source vs AI taxonomy mismatches
    - DUPLICATE_CANDIDATES: Count of controls with high similarity scores

    Heatmap dimensions: risk_theme, owning_function, owning_location
    Heatmap metrics: COUNT, PCT_INCOMPLETE, PCT_MISSING_EVIDENCE
    """,
)
async def controls_analytics(
    metrics: list[str] = ["TOTAL", "DOC_COMPLETENESS", "EVIDENCE_READY"],
    heatmaps: list[dict] = [],  # [{"x": "risk_theme", "y": "owning_function", "metric": "COUNT"}]
    filters: dict = {},
) -> dict:
    """
    Returns KPIs and heatmap data.
    """
```

#### Tool 5: `controls_find_similar`

```python
@mcp_tool(
    name="controls_find_similar",
    description="""Find controls similar to a seed control using vector embeddings.

    Use this tool to:
    - Find duplicate or near-duplicate controls
    - Discover standard control patterns
    - Identify controls with inconsistent mappings
    - Suggest consolidation candidates

    Similarity is computed using cosine similarity on embedding vectors.
    Multiple embedding fields can be weighted differently.

    embedding_fields options:
    - control_description_embedding (most common)
    - control_title_embedding
    - evidence_description_embedding
    - combined (weighted average)
    """,
)
async def controls_find_similar(
    seed_control_id: str,  # The control to find similar controls for
    embedding_field: str = "control_description_embedding",
    threshold: float = 0.75,  # Minimum similarity score (0-1)
    limit: int = 10,
    filters: dict = {},
) -> dict:
    """
    Returns list of similar controls with scores and mismatches.
    """
```

#### Tool 6: `controls_history`

```python
@mcp_tool(
    name="controls_history",
    description="""Get change history for controls.

    Use this tool to:
    - See what changed since a specific date
    - Track new, deactivated, or modified controls
    - View diff between two versions of a control
    - Generate change reports for audit/review cycles

    Change types:
    - NEW: Newly created controls
    - DEACTIVATED: Controls that became inactive
    - FREQUENCY_CHANGED: Execution frequency changed
    - TYPE_CHANGED: Preventative/Detective changed
    - DOC_QUALITY_CHANGED: Documentation completeness changed
    - MAPPING_CHANGED: Risk theme mapping changed
    """,
)
async def controls_history(
    from_date: str,  # YYYY-MM-DD
    to_date: str = None,  # YYYY-MM-DD, defaults to today
    change_types: list[str] = None,  # Filter by change type
    control_id: str = None,  # Optional: history for specific control
    limit: int = 50,
) -> dict:
    """
    Returns change summary and event list.
    """
```

### 6.4 Backend Implementation Files

#### File: `server/pipelines/controls/api/controls_api.py`

```python
"""Controls Command Center API endpoints.

This module provides REST API endpoints for the Controls Command Center,
designed to be consumed by both the frontend and as MCP tools for agents.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import date

from server.auth.helpers import get_token_from_header, get_access_control
from server.pipelines.controls.consumer import ControlsConsumer
from server.pipelines.controls.consumer.analytics import AnalyticsService
from server.pipelines.controls.consumer.search import SearchService
from server.pipelines.controls.consumer.snapshot import SnapshotResolver

router = APIRouter(prefix="/api/controls", tags=["controls"])


# --- Request/Response Models ---

class AsOfSpec(BaseModel):
    mode: Literal["CURRENT", "DATE"] = "CURRENT"
    date: Optional[str] = None  # YYYY-MM-DD
    timezone: str = "UTC"


class ResolvedAsOf(BaseModel):
    requested: AsOfSpec
    resolved_to: str
    resolution_rule: Literal["CURRENT", "EXACT", "NEAREST_BEFORE_ELSE_CURRENT"]


class FilterSpec(BaseModel):
    owning_function_ids: List[str] = []
    owning_location_ids: List[str] = []
    hierarchy_level: List[str] = []
    control_status: List[str] = ["Active"]
    risk_theme_ids: List[str] = []
    preventative_detective: List[str] = []
    manual_automated: List[str] = []
    execution_frequency: List[str] = []
    quality_flags: Dict[str, Optional[bool]] = {}


class PageSpec(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class SortSpec(BaseModel):
    field: str
    dir: Literal["asc", "desc"] = "asc"


# --- Endpoints ---

@router.post("/list")
async def list_controls(
    as_of: AsOfSpec = AsOfSpec(),
    filters: FilterSpec = FilterSpec(),
    sort: List[SortSpec] = [SortSpec(field="control_id")],
    page: PageSpec = PageSpec(),
    include: Dict[str, bool] = {},
    columns: List[str] = [],
    token: str = Depends(get_token_from_header),
):
    """List controls with filtering, sorting, and pagination."""
    access = await get_access_control(token)
    if not access.has_dashboard_access:
        raise HTTPException(status_code=403, detail="Dashboard access required")

    async with ControlsConsumer() as consumer:
        # Resolve as-of date
        resolver = SnapshotResolver(consumer)
        resolved = await resolver.resolve(as_of)

        # Build and execute query
        # ... implementation

    return {
        "resolved_as_of": resolved,
        "total": total,
        "rows": rows,
    }


@router.post("/search")
async def search_controls(
    query: str,
    mode: Literal["KEYWORD", "SEMANTIC", "HYBRID"] = "HYBRID",
    # ... other params
):
    """Search controls using FTS, semantic, or hybrid search."""
    # ... implementation


@router.get("/{control_id}")
async def get_control(
    control_id: str,
    as_of_date: Optional[str] = None,
    include_history: bool = False,
    include_similar: bool = False,
):
    """Get a single control with full details."""
    # ... implementation


@router.post("/analytics/overview")
async def get_overview_analytics(
    as_of: AsOfSpec = AsOfSpec(),
    filters: FilterSpec = FilterSpec(),
    metrics: List[str] = ["TOTAL", "DOC_COMPLETENESS"],
    heatmaps: List[Dict] = [],
):
    """Get portfolio overview KPIs and heatmaps."""
    # ... implementation


@router.post("/similar")
async def find_similar_controls(
    seed_control_id: str,
    embedding_fields: List[str] = ["control_description_embedding"],
    threshold: float = 0.75,
    k: int = 20,
):
    """Find similar controls using embeddings."""
    # ... implementation


@router.post("/changes")
async def get_changes(
    from_date: str,
    to_date: Optional[str] = None,
    change_types: List[str] = None,
):
    """Get changes between two dates."""
    # ... implementation
```

#### File: `server/pipelines/controls/consumer/analytics.py`

```python
"""Analytics service for computing KPIs and aggregations."""

from typing import Dict, List, Any
from dataclasses import dataclass

from server.pipelines.controls.consumer.service import ControlsConsumer


@dataclass
class KPIResult:
    total: int
    doc_completeness_pct: float
    evidence_ready_pct: float
    stale_180d_pct: float
    mapping_conflicts: int
    duplicate_candidates: int


class AnalyticsService:
    """Service for computing portfolio analytics."""

    def __init__(self, consumer: ControlsConsumer):
        self.consumer = consumer

    async def compute_kpis(self, filters: dict) -> KPIResult:
        """Compute portfolio KPIs."""
        # Query controls and enrichment data
        # Compute metrics
        # ... implementation

    async def compute_heatmap(
        self,
        x_field: str,
        y_field: str,
        metric: str,
        filters: dict,
    ) -> List[Dict]:
        """Compute heatmap cells."""
        # ... implementation

    async def compute_doc_completeness_matrix(
        self,
        group_by: str,  # "owning_function" or "owning_location"
        filters: dict,
    ) -> Dict:
        """Compute documentation completeness matrix."""
        # ... implementation
```

#### File: `server/pipelines/controls/consumer/search.py`

```python
"""Search service with FTS, semantic, and hybrid modes."""

from typing import List, Dict, Any, Literal
from dataclasses import dataclass

from server.pipelines.controls.consumer.service import ControlsConsumer


@dataclass
class SearchResult:
    control_id: str
    control_title: str
    score: float
    breakdown: Dict[str, float]
    highlights: Dict[str, str]


class SearchService:
    """Service for control search operations."""

    def __init__(self, consumer: ControlsConsumer):
        self.consumer = consumer

    async def keyword_search(
        self,
        query: str,
        fields: List[str],
        filters: dict,
        limit: int,
    ) -> List[SearchResult]:
        """Full-text search using BM25."""
        # Use existing FTS indexes on ai_controls_model_cleaned_text_current
        # ... implementation

    async def semantic_search(
        self,
        query: str,
        embedding_fields: List[str],
        filters: dict,
        limit: int,
    ) -> List[SearchResult]:
        """Semantic search using embeddings."""
        # Generate query embedding
        # Compute cosine similarity
        # ... implementation

    async def hybrid_search(
        self,
        query: str,
        fts_fields: List[str],
        embedding_fields: List[str],
        filters: dict,
        fts_weight: float = 0.4,
        semantic_weight: float = 0.6,
        limit: int = 50,
    ) -> List[SearchResult]:
        """Hybrid search combining FTS and semantic."""
        # Get FTS results
        fts_results = await self.keyword_search(query, fts_fields, filters, limit)

        # Get semantic results
        semantic_results = await self.semantic_search(query, embedding_fields, filters, limit)

        # Apply RRF fusion
        fused = self._rrf_fusion(fts_results, semantic_results, fts_weight, semantic_weight)

        return fused[:limit]

    def _rrf_fusion(
        self,
        fts_results: List[SearchResult],
        semantic_results: List[SearchResult],
        fts_weight: float,
        semantic_weight: float,
        k: int = 60,
    ) -> List[SearchResult]:
        """Reciprocal Rank Fusion."""
        # RRF score = sum(weight / (k + rank))
        # ... implementation
```

#### File: `server/pipelines/controls/mcp/tools.py`

```python
"""MCP Tool definitions for Controls Command Center.

These tools are designed for agent consumption following Anthropic's
best practices for tool design.
"""

from typing import Literal, Optional, List, Dict, Any

# Tool definitions will be registered with the MCP server
# Following the patterns from https://www.anthropic.com/engineering/writing-tools-for-agents

TOOLS = [
    {
        "name": "controls_search",
        "description": """Search for controls using keyword, semantic, or hybrid search.

Use this tool to:
- Find controls by keyword (e.g., "reconciliation", "daily", "evidence")
- Find semantically similar controls to a description
- Combine keyword and semantic search for best results

The tool returns control IDs, titles, and relevance scores.
Use response_format="concise" for quick lookups, "detailed" for full context.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query text"
                },
                "mode": {
                    "type": "string",
                    "enum": ["KEYWORD", "SEMANTIC", "HYBRID"],
                    "default": "HYBRID",
                    "description": "Search mode"
                },
                "search_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["control_title", "control_description"],
                    "description": "Fields to search in"
                },
                "filters": {
                    "type": "object",
                    "default": {},
                    "description": "Optional filters like {\"control_status\": [\"Active\"]}"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum results to return"
                },
                "response_format": {
                    "type": "string",
                    "enum": ["concise", "detailed"],
                    "default": "concise",
                    "description": "Response detail level"
                }
            },
            "required": ["query"]
        }
    },
    # ... other tool definitions
]
```

---

## 7. Component Specifications

### 9.1 State Management

**File: `client/src/context/ControlsContext.tsx`**

```typescript
interface ControlsState {
  // Global state
  asOf: AsOfSpec;
  resolvedAsOf: string | null;
  filters: FilterSpec;

  // Search state
  searchQuery: string;
  searchMode: 'KEYWORD' | 'SEMANTIC' | 'HYBRID';
  searchFields: string[];

  // UI state
  selectedControlIds: string[];
  expandedControlId: string | null;
  drawerControlId: string | null;

  // Saved views
  savedViews: SavedView[];
}

interface ControlsActions {
  setAsOf: (spec: AsOfSpec) => void;
  setFilters: (filters: Partial<FilterSpec>) => void;
  resetFilters: () => void;
  setSearchQuery: (query: string) => void;
  selectControl: (controlId: string) => void;
  openDrawer: (controlId: string) => void;
  closeDrawer: () => void;
  saveView: (name: string) => void;
  loadView: (viewId: string) => void;
}
```

### 9.2 Custom Hooks

**File: `client/src/hooks/controls/useControlsFilters.ts`**

```typescript
export function useControlsFilters() {
  const { filters, setFilters, resetFilters } = useControlsContext();

  // Filter presets
  const applyPreset = (presetName: string) => {
    const presets = {
      'active-only': { control_status: ['Active'] },
      'missing-evidence': { quality_flags: { missing_evidence: true } },
      'high-risk': { risk_theme_ids: ['CYBER_INFOSEC', 'FINANCIAL_CRIME'] },
    };
    setFilters(presets[presetName]);
  };

  // Derived state
  const activeFilterCount = useMemo(() => {
    return Object.values(filters).filter(v =>
      Array.isArray(v) ? v.length > 0 : v !== null
    ).length;
  }, [filters]);

  return { filters, setFilters, resetFilters, applyPreset, activeFilterCount };
}
```

**File: `client/src/hooks/controls/useAsOfDate.ts`**

```typescript
export function useAsOfDate() {
  const { asOf, setAsOf, resolvedAsOf } = useControlsContext();

  const setCurrentMode = () => setAsOf({ mode: 'CURRENT', date: null, timezone: 'UTC' });

  const setHistoricalDate = (date: string) =>
    setAsOf({ mode: 'DATE', date, timezone: 'UTC' });

  const formattedResolved = useMemo(() => {
    if (!resolvedAsOf) return null;
    return formatDate(resolvedAsOf);
  }, [resolvedAsOf]);

  return { asOf, setCurrentMode, setHistoricalDate, resolvedAsOf, formattedResolved };
}
```

---

## 8. Mock Data Strategy

### 10.1 Mock Data Files

**File: `client/src/services/controls/mockData.ts`**

```typescript
// Generate realistic mock data for development

export const mockRiskThemes = [
  { risk_theme_id: '1.1', risk_theme_name: 'Technology, Product and Infrastructure Stability' },
  { risk_theme_id: '1.2', risk_theme_name: 'Cyber and Information Security' },
  { risk_theme_id: '1.3', risk_theme_name: 'Data Management' },
  // ... all 23 NFR categories
];

export const mockFunctions = [
  { function_id: 'N14952', function_name: 'Investment Bank' },
  { function_id: 'N10007', function_name: 'Global Markets' },
  // ... more functions
];

export const mockLocations = [
  { location_id: '2210', location_name: 'UBS ESE-Frankfurt' },
  { location_id: 'C782', location_name: 'London' },
  // ... more locations
];

// Generate N mock controls
export function generateMockControls(count: number): ControlRow[] {
  return Array.from({ length: count }, (_, i) => ({
    control_id: `CTRL-${String(i + 1).padStart(10, '0')}`,
    control_title: generateMockTitle(),
    hierarchy_level: Math.random() > 0.3 ? 'Level 2' : 'Level 1',
    control_status: Math.random() > 0.1 ? 'Active' : 'Inactive',
    owning_function_id: randomPick(mockFunctions).function_id,
    owning_location_id: randomPick(mockLocations).location_id,
    preventative_detective: randomPick(['Preventative', 'Detective']),
    manual_automated: randomPick(['Manual', 'Automated', 'IT dependent automated']),
    execution_frequency: randomPick(['Daily', 'Weekly', 'Monthly', 'Quarterly', 'Event Triggered']),
    last_modified_on: randomDate(365),
    risk_themes: [randomPick(mockRiskThemes)],
    quality: {
      doc_completeness_score: Math.random(),
      missing: randomSubset(['what', 'who', 'when', 'where', 'why', 'evidence', 'escalation']),
      has_abbreviations: Math.random() > 0.7,
    },
  }));
}

// Mock API responses
export const mockListResponse = (page: PageSpec, filters: FilterSpec) => {
  const allControls = generateMockControls(500);
  // Apply filters, pagination
  // ...
  return {
    resolved_as_of: { requested: { mode: 'CURRENT' }, resolved_to: new Date().toISOString() },
    total: filteredControls.length,
    rows: paginatedControls,
  };
};
```

### 10.2 Mock API Service

**File: `client/src/services/controls/api.ts`**

```typescript
import { mockListResponse, mockControlDetails, mockAnalyticsOverview } from './mockData';

const USE_MOCK = process.env.REACT_APP_USE_MOCK === 'true';

export const controlsApi = {
  list: async (params: ListParams): Promise<ListResponse> => {
    if (USE_MOCK) {
      await delay(300); // Simulate network latency
      return mockListResponse(params.page, params.filters);
    }
    return fetch('/api/controls/list', { method: 'POST', body: JSON.stringify(params) })
      .then(r => r.json());
  },

  get: async (controlId: string, options?: GetOptions): Promise<ControlDetails> => {
    if (USE_MOCK) {
      await delay(200);
      return mockControlDetails(controlId);
    }
    const params = new URLSearchParams(options as any);
    return fetch(`/api/controls/${controlId}?${params}`).then(r => r.json());
  },

  search: async (params: SearchParams): Promise<SearchResponse> => {
    if (USE_MOCK) {
      await delay(400);
      return mockSearchResponse(params);
    }
    return fetch('/api/controls/search', { method: 'POST', body: JSON.stringify(params) })
      .then(r => r.json());
  },

  analyticsOverview: async (params: AnalyticsParams): Promise<OverviewResponse> => {
    if (USE_MOCK) {
      await delay(500);
      return mockAnalyticsOverview(params);
    }
    return fetch('/api/controls/analytics/overview', { method: 'POST', body: JSON.stringify(params) })
      .then(r => r.json());
  },

  // ... other methods
};
```

---

## 9. Testing Strategy

### 9.1 Frontend Testing

**Unit Tests (Jest + React Testing Library)**
- Component rendering tests
- Hook behavior tests
- Filter logic tests
- Mock data generation tests

**Integration Tests**
- Page-level tests with mock API
- Navigation flow tests
- Filter → data grid → detail flow

**E2E Tests (Cypress/Playwright)**
- Full user flows
- Cross-browser testing
- Performance testing

### 9.2 Backend Testing

**Unit Tests (pytest)**
- Service method tests
- Query builder tests
- Analytics calculation tests

**Integration Tests**
- API endpoint tests with test database
- Search functionality tests
- Snapshot resolver tests

**MCP Tool Tests**
- Tool input validation
- Response format tests
- Error handling tests

---

## 10. Risk & Dependencies

### 10.1 Technical Risks

| Risk | Mitigation |
|------|------------|
| SurrealDB FTS performance at scale | Pre-compute analytics, use pagination, add caching layer |
| Embedding similarity computation cost | Pre-compute similarity matrices, use approximate nearest neighbors |
| Large response payloads | Implement streaming, pagination, column selection |
| Complex filter combinations | Build query incrementally, add query plan analysis |

### 10.2 Dependencies

**Phase 1 (UI with Mock):**
- No external dependencies
- Can proceed independently of backend

**Phase 2 (Backend Integration):**
- Depends on existing SurrealDB schema
- Depends on existing consumer service patterns
- May need schema additions for new indexes

### 10.3 Open Questions for Clarification

1. **Vector Search Implementation**: Should we use SurrealDB's native vector search (when available) or compute similarity in Python?

2. **Caching Strategy**: Should we implement Redis caching for frequently accessed analytics, or rely on SurrealDB's query caching?

3. **Real-time Updates**: Should the dashboard support real-time updates (WebSocket) or polling?

4. **Export Format**: Besides CSV/Parquet, should we support other export formats (Excel, PDF reports)?

5. **Access Control Granularity**: Should we implement row-level security based on owning function/location?

---

## Appendix A: File Creation Checklist

### Phase 1 Files to Create

```
client/src/
├── pages/Controls/
│   ├── index.tsx
│   ├── ControlsLayout.tsx
│   ├── Overview/
│   │   └── ControlsOverview.tsx
│   ├── Explorer/
│   │   └── ControlsExplorer.tsx
│   ├── Quality/
│   │   └── ControlsQuality.tsx
│   ├── Similarity/
│   │   └── ControlsSimilarity.tsx
│   ├── History/
│   │   └── ControlsHistory.tsx
│   ├── Details/
│   │   └── ControlDetails.tsx
│   └── components/
│       ├── AsOfDatePicker.tsx
│       ├── FilterRail.tsx
│       ├── GlobalSearchBar.tsx
│       ├── ControlsDataGrid.tsx
│       ├── ChartCard.tsx
│       ├── HeatmapChart.tsx
│       ├── StackedBarChart.tsx
│       ├── ControlDrawer.tsx
│       ├── GuidelineCoach.tsx
│       ├── CompareModal.tsx
│       ├── DiffViewer.tsx
│       └── ControlsSidebar.tsx
├── context/
│   └── ControlsContext.tsx
├── hooks/controls/
│   ├── useControlsFilters.ts
│   ├── useAsOfDate.ts
│   ├── useControlsSearch.ts
│   └── useControlsAnalytics.ts
└── services/controls/
    ├── api.ts
    ├── types.ts
    └── mockData.ts
```

### Phase 2 Files to Create

```
server/pipelines/controls/
├── api/
│   └── controls_api.py
├── consumer/
│   ├── analytics.py
│   ├── search.py
│   └── snapshot.py
└── mcp/
    ├── __init__.py
    └── tools.py
```

---

## Appendix B: JSON Schema Definitions

See the user's original specification for complete JSON schemas for:
- `AsOfSpec` / `ResolvedAsOf`
- `FilterSpec`
- `PageSpec` / `SortSpec`
- `ControlRow` / `ControlDetails`
- `SearchResult`
- `AnalyticsResponse`
- `HeatmapCell`
- `ChangeEvent`

These schemas should be implemented in both TypeScript (frontend) and Pydantic (backend) for full type safety.
