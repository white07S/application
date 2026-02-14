# Common Filter Panel — UI Requirements

> **Purpose**: A reusable, collapsible sidebar filter panel that serves as the primary data scoping mechanism across all explorer views. All downstream data (controls, assessments, reports) will be filtered through these selections.

---

## 1. Layout & Structure

### Panel Behavior
- **Position**: Left sidebar, overlaying or pushing content depending on screen width.
- **Default state**: Collapsed — shows a thin vertical strip with a filter icon and a badge count of active filters.
- **Expanded state**: 280–320px wide panel slides in from the left.
- **Toggle**: Click the filter icon strip or a dedicated expand/collapse button.
- **Persistence**: Filter selections persist across page navigation within the session. Panel open/close state persists per session.

### Panel Anatomy (top to bottom)
```
┌──────────────────────────────┐
│  ⊞ Filters          [⟲] [✕] │  ← Header: title, reset-all, collapse
│  ─────────────────────────── │
│  Cascade mode: [toggle]      │  ← Cascade toggle (see §5)
│  ─────────────────────────── │
│  📅 As of Date               │  ← Section 1
│  ─────────────────────────── │
│  🏢 Functions                │  ← Section 2 (collapsible)
│  ─────────────────────────── │
│  📍 Locations                │  ← Section 3 (collapsible)
│  ─────────────────────────── │
│  🏛 Consolidated Entity      │  ← Section 4 (collapsible)
│  ─────────────────────────── │
│  📋 Assessment Units         │  ← Section 5 (collapsible)
│  ─────────────────────────── │
│  ⚠ Risk Themes              │  ← Section 6 (collapsible)
│  ─────────────────────────── │
│                              │
│        [ Apply Filters ]     │  ← Sticky bottom button
│  Active: 3 filters           │  ← Summary line
└──────────────────────────────┘
```

### Section Collapse
- Each filter section is independently collapsible via its header.
- When collapsed, the header shows a **compact summary** of active selections (e.g., "3 selected" or the first selection name + "+2 more").
- Clicking the section header toggles expand/collapse.
- A small clear icon (✕) on the section header clears that section's selections.

---

## 2. Filter Sections

### 2.1 As of Date

**Purpose**: Sets the temporal query point. All versioned data (functions, locations, assessment units, risk themes) is resolved as of this timestamp using the `tx_from / tx_to` temporal range.

**Component**: Single date picker.

**Behavior**:
- Default value: **Today** (current date).
- Date format: `DD MMM YYYY` (e.g., `13 Feb 2026`).
- Calendar dropdown opens on click; also allows manual text input.
- Selecting a date immediately updates the date value in the sidebar (live).
- A "Today" shortcut button inside the calendar resets to current date.
- No future dates allowed — max date is today.

**Display**:
```
As of Date
┌─────────────────────────────┐
│  📅  13 Feb 2026        [▾] │
└─────────────────────────────┘
```

---

### 2.2 Functions (Hierarchical Tree)

**Purpose**: Filter by organizational function hierarchy.

**Hierarchy** (7 levels, top → leaf):
```
Group → Division → Unit → Area → Sector → Segment → Function
```

**Component**: Searchable, navigable tree dropdown with multi-select.

#### Search Bar
- Placed at the top of the section.
- Placeholder: `Search by ID or name...`
- Searches across **all levels** of the hierarchy.
- Results appear as a flat filtered list below the search bar, each item showing:
  - Its **level label** as a muted tag (e.g., `DIVISION`, `FUNCTION`).
  - Its **name** and **ID** side by side.
  - Its **breadcrumb path** in small muted text below (e.g., `Group A > Division B > Unit C`).

#### Auto-Fill Behavior
- When the user selects a node (by search or tree navigation):
  - **All parent nodes** up to the root are auto-filled / highlighted in the tree as context (not as active selections, but visually shown as the ancestry path).
  - If the node is a **mid-level** node: only parents are shown as context. Children are NOT auto-selected.
  - If the node is a **leaf** (Function): all parents are shown as context path.
- The breadcrumb path is always visible for any selected node.

#### Tree Navigation
- Default view (no search): shows the top level (Groups) as expandable rows.
- Clicking a chevron `▸` on a node expands it to show its children.
- Each level indents further (use 16px indent per level).
- Nodes show: `[checkbox] [expand chevron] Name (ID)` — with record count badge if available.
- Checkboxes enable multi-select at any level.

#### Multi-Select
- User can select multiple nodes at different levels.
- Selections are shown as **chips** below the search bar.
- Each chip shows: `Name (Level)` with an ✕ to remove.
- If more than 3 chips, collapse into `Function A, Function B +2 more` format.

**Display when collapsed**:
```
Functions                              ✕
  ┌─ Division B, Function X +1 more
```

**Display when expanded**:
```
Functions                              ✕
┌─────────────────────────────┐
│  🔍 Search by ID or name... │
└─────────────────────────────┘
  [ Division B ✕ ] [ Function X ✕ ] [ Unit C ✕ ]

  ▸ Group A
  ▾ Group B
      ▸ Division B₁
      ▾ Division B₂  ☑
          ▸ Unit C₁
          ▸ Unit C₂
  ▸ Group C
```

---

### 2.3 Locations (Hierarchical Tree)

**Purpose**: Filter by location hierarchy.

**Hierarchy** (5 levels, top → leaf):
```
Location → Region → Sub Region → Country → Company
```

**Component**: Identical interaction pattern to Functions (§2.2) — searchable tree dropdown with multi-select, auto-fill of parents, breadcrumb paths, and chips.

**Only difference**: Level labels and hierarchy depth (5 levels vs 7).

**Search placeholder**: `Search by ID or name...`

**Display**: Same structure as Functions.

---

### 2.4 Consolidated Entity

**Purpose**: Filter by consolidated legal entity.

**Structure**: Flat list (no hierarchy). Each entity has an ID and a name.

**Component**: Searchable dropdown with multi-select.

#### Search Bar
- Placeholder: `Search by ID or name...`
- Filters the flat list as the user types.
- Each result row shows: **Name** and **ID** (muted, right-aligned or below).

#### Selection
- Multi-select via checkboxes.
- Selections shown as chips below the search bar.

**Display**:
```
Consolidated Entity                    ✕
┌─────────────────────────────┐
│  🔍 Search by ID or name... │
└─────────────────────────────┘
  [ Entity A ✕ ] [ Entity B ✕ ]

  ☑ Entity A               CE-001
  ☑ Entity B               CE-002
  ☐ Entity C               CE-003
  ☐ Entity D               CE-004
```

---

### 2.5 Assessment Units

**Purpose**: Filter by assessment unit.

**Structure**: Flat list. Each unit has an ID, name, and status (Active / Inactive).

**Component**: Searchable dropdown with multi-select and status visibility.

#### Search Bar
- Placeholder: `Search by ID or name...`

#### Result Rows
Each row shows:
```
  ☐  Unit Name                    AU-042
     ● Active
```
- **Name**: Primary text, left-aligned.
- **ID**: Muted text, right-aligned.
- **Status indicator**: Small colored dot + label below the name.
  - `Active` → green dot (`#22C55E`)
  - `Inactive` → gray dot (`#9CA3AF`)

#### Optional: Status Quick Filter
- Small toggle pills above the list: `All | Active | Inactive`
- Allows quickly filtering the list to only active or inactive units.

**Display**:
```
Assessment Units                       ✕
┌─────────────────────────────┐
│  🔍 Search by ID or name... │
└─────────────────────────────┘
  ( All ) ( Active ) ( Inactive )

  [ Unit Alpha ✕ ]

  ☑ Unit Alpha                  AU-001
     ● Active
  ☐ Unit Beta                   AU-002
     ● Active
  ☐ Unit Gamma                  AU-003
     ○ Inactive
```

---

### 2.6 Risk Themes

**Purpose**: Filter by risk taxonomy and/or individual risk themes.

**Hierarchy** (2 levels):
```
Taxonomy → Risk Theme
```

**Component**: Searchable, expandable grouped list with multi-select.

#### Search Bar
- Placeholder: `Search by taxonomy or theme ID / name...`
- Searches across **both** taxonomy names/IDs and risk theme names/IDs.
- Results show which level matched with a tag (`TAXONOMY` or `THEME`).

#### Auto-Fill Behavior
- Selecting a **Risk Theme** → its parent Taxonomy is shown as context (highlighted, not selected).
- Selecting a **Taxonomy** → selects the taxonomy level. Does NOT auto-select all child themes.

#### Display
Taxonomies are shown as expandable group headers. Themes are listed under their parent taxonomy.

```
Risk Themes                            ✕
┌─────────────────────────────┐
│  🔍 Search by ID or name... │
└─────────────────────────────┘
  [ Credit Risk ✕ ] [ Ops Failure ✕ ]

  ▾ Credit Risk Taxonomy        TAX-01
      ☑ Credit Risk             RT-001
      ☐ Concentration Risk      RT-002
      ☐ Settlement Risk         RT-003
  ▸ Operational Risk Taxonomy   TAX-02
  ▸ Market Risk Taxonomy        TAX-03
```

---

## 3. Cascade Mode & Conflict Indicators

### Cascade Toggle
- Located at the top of the panel, below the header.
- Small toggle switch with label: **"Link filters"** (or "Cascade").
- **ON** (linked): Selecting a value in one filter narrows the available options in downstream filters to only related records. Direction of cascade:
  - `Function` → narrows `Assessment Units` (to AUs assigned to selected functions)
  - `Location` → narrows `Consolidated Entity` (to CEs mapped to selected locations)
  - `Location` → narrows `Assessment Units` (to AUs assigned to selected locations)
  - `Risk Theme` selections do NOT cascade to other filters (independent).
  - `As of Date` always cascades — all versioned data resolves to this date.
- **OFF** (independent): All filters show their full unfiltered lists. Conflict indicators appear instead.

### Conflict Indicators (Cascade OFF)
When cascade is disabled and the user makes selections that have no overlapping data, show a **subtle warning**:
- A small amber dot or triangle icon (⚠) next to the conflicting filter section header.
- Tooltip on hover: `"No assessment units match the selected functions."`
- The Apply button shows a warning state: `Apply (potential conflicts)`.
- This is informational only — the user can still apply conflicting filters.

### Cascaded Option Styling
When cascade is ON and a downstream filter's options are narrowed:
- Show a small info line at the top of the narrowed section: `Filtered by: Function (3)` with a link to clear the upstream dependency.
- Options that would exist but are excluded by cascade are either hidden entirely OR shown at the bottom in a muted, disabled state with a label like `"Not matching current filters"` — designer to explore which feels cleaner.

---

## 4. Selection & Apply Flow

### Live Sidebar Updates
- All interactions within the sidebar (searching, expanding trees, checking/unchecking) update the sidebar UI **immediately**.
- The sidebar is a self-contained selection workspace — no API calls happen until Apply.

### Apply Button
- **Sticky** at the bottom of the panel. Always visible regardless of scroll position.
- Label: `Apply Filters`
- **Disabled** when no changes have been made since last apply.
- **Enabled + highlighted** when selections differ from the currently applied state.
- Visual diff: Show a small change indicator (e.g., `"2 changes"`) on the button when there are unapplied changes.
- On click: triggers data fetch across all explorer views with the selected filter criteria.
- Brief loading state on the button while data loads, then returns to disabled (no pending changes).

### Reset
- **Reset All**: Button in the panel header (⟲ icon). Clears all filter sections back to defaults (date = today, all selections cleared).
- **Per-section reset**: Small ✕ on each section header clears only that section.
- Reset actions are also "pending" — they take effect in the sidebar immediately but require Apply to update the explorer data.

### Active Filter Summary
- Below the Apply button: `Active: N filters` — count of non-default filter sections.
- When panel is **collapsed**: the thin strip shows the filter icon with a badge count of active filters.

---

## 5. Visual Specifications

### Design Language
Dense, professional, data-tool aesthetic. Think Bloomberg terminal meets modern SaaS — compact but not cramped, information-rich but scannable.

### Panel
| Property | Value |
|---|---|
| Width (expanded) | 300px |
| Background | `#FFFFFF` (white) |
| Border right | `1px solid` border-light (`#E5E7EB`) |
| Shadow | `0 1px 3px rgba(0,0,0,0.06)` — subtle, only on the right edge |
| Header bg | `#F9FAFB` (surface-light) |
| Z-index | Above content, below modals |

### Collapsed Strip
| Property | Value |
|---|---|
| Width | 40px |
| Background | `#F9FAFB` |
| Icon | Material: `filter_list`, 20px, `#6B7280` |
| Badge | 16px circle, `#3B82F6` bg, white text, top-right of icon |

### Typography
| Element | Size | Weight | Color |
|---|---|---|---|
| Panel title ("Filters") | 13px | 600 (semibold) | `#111827` (text-main) |
| Section header | 11px | 600 | `#111827` |
| Search input text | 12px | 400 | `#111827` |
| Search placeholder | 12px | 400 | `#9CA3AF` |
| Tree node name | 12px | 400 | `#111827` |
| Tree node ID | 11px | 400 | `#9CA3AF` |
| Breadcrumb path | 10px | 400 | `#9CA3AF` |
| Level tag (e.g., DIVISION) | 9px | 600 | `#6B7280` on `#F3F4F6` bg |
| Chip text | 11px | 500 | `#1E40AF` on `#EFF6FF` bg |
| Status label | 10px | 500 | green/gray per status |
| Apply button | 12px | 600 | white on `#2563EB` |

### Spacing
| Element | Value |
|---|---|
| Panel padding (horizontal) | 12px |
| Section padding (vertical) | 10px top, 8px bottom |
| Section header margin bottom | 6px |
| Search bar height | 32px |
| Search bar padding | 6px 10px |
| Tree row height | 28px |
| Tree indent per level | 16px |
| Chip height | 22px |
| Chip padding | 2px 8px |
| Chip gap | 4px |
| Chip margin below search | 6px |
| Checkbox size | 14px × 14px |
| Section divider | `1px solid #F3F4F6` |
| Apply button height | 36px |
| Apply button margin | 12px horizontal, 8px vertical |
| Bottom bar padding | 8px 12px |

### Colors
| Role | Value | Usage |
|---|---|---|
| Primary blue | `#2563EB` | Apply button, active toggle, selected accent |
| Primary blue light | `#EFF6FF` | Chip background, selected row highlight |
| Primary blue text | `#1E40AF` | Chip text |
| Green (active) | `#22C55E` | Active status dot |
| Gray (inactive) | `#9CA3AF` | Inactive status dot, muted text |
| Amber (conflict) | `#F59E0B` | Conflict indicator dot / triangle |
| Surface light | `#F9FAFB` | Section header bg, hover states |
| Surface alt | `#F3F4F6` | Level tags, badge bg |
| Border light | `#E5E7EB` | Dividers, input borders, tree lines |
| Text main | `#111827` | Primary text |
| Text sub | `#6B7280` | Secondary text |
| Text muted | `#9CA3AF` | IDs, placeholders, breadcrumbs |

### Interactions
| State | Style |
|---|---|
| Hover (tree row) | bg `#F9FAFB`, slight transition (150ms) |
| Hover (chip ✕) | ✕ icon turns `#DC2626` (red) |
| Selected row | bg `#EFF6FF`, left border `2px solid #2563EB` |
| Disabled option (cascaded out) | opacity `0.4`, no pointer events |
| Search focus | border `#2563EB`, ring `0 0 0 2px #BFDBFE` |
| Apply button hover | bg `#1D4ED8` |
| Apply button disabled | bg `#93C5FD`, cursor not-allowed |
| Apply button pending | bg `#2563EB` + subtle pulse or `"2 changes"` badge |
| Expand/collapse chevron | Rotates 90° on expand, transition 150ms |

### Icons
Use **Material Symbols Outlined** (consistent with existing app):
| Filter | Icon |
|---|---|
| As of Date | `calendar_today` |
| Functions | `account_tree` |
| Locations | `location_on` |
| Consolidated Entity | `domain` |
| Assessment Units | `assignment` |
| Risk Themes | `warning` |
| Cascade toggle | `link` (on) / `link_off` (off) |
| Search | `search` |
| Clear section | `close` (12px) |
| Reset all | `restart_alt` |
| Expand | `chevron_right` |
| Collapse | `expand_more` |
| Conflict warning | `error_outline` (amber) |

---

## 6. States & Edge Cases

### Empty States
- **No search results**: Show `No matches for "xyz"` in muted text centered in the list area.
- **Empty list (no data)**: Show `No data available` with the section's icon in muted style.
- **Cascade narrows to zero**: Show `No items match linked filters` with an option to unlink (turn off cascade for that section).

### Loading States
- When tree data is loading (first load): Show 3-4 skeleton rows (animated shimmer) matching the row height.
- When Apply is in progress: Apply button shows a small spinner, label changes to `Applying...`.

### Overflow
- If a section has many items (e.g., 500+ assessment units), virtualize the list. Only render visible rows.
- Scrollable area within each section, max height ~200px before scrolling. The panel itself also scrolls if all sections are expanded.

### Keyboard Navigation
- `Tab` moves between sections and interactive elements.
- Arrow keys navigate within tree nodes.
- `Enter` / `Space` toggles checkbox or expands node.
- `Escape` closes search results overlay or collapses the panel.
- Typing in a focused section auto-focuses the search input.

### Responsive
- On screens < 1024px: Panel becomes a full-height overlay with a backdrop dim.
- On screens ≥ 1024px: Panel pushes content to the right.
- On screens ≥ 1440px: Panel can remain open by default (user preference).

---

## 7. Data Summary

Quick reference for what each filter operates on:

| Filter | Data Shape | Levels | Searchable By | Multi-Select |
|---|---|---|---|---|
| As of Date | Single date | — | Calendar / text | No |
| Functions | Hierarchical tree | 7 (Group → Function) | ID, name | Yes |
| Locations | Hierarchical tree | 5 (Location → Company) | ID, name | Yes |
| Consolidated Entity | Flat list | 1 | ID, name | Yes |
| Assessment Units | Flat list + status | 1 | ID, name | Yes |
| Risk Themes | Grouped (2-level) | 2 (Taxonomy → Theme) | Taxonomy ID/name, Theme ID/name | Yes |

---

## 8. Open Design Questions

These are intentionally left for the designer to explore and propose approaches:

1. **Tree connector lines**: Should tree views show vertical/horizontal connector lines between parent-child nodes (VS Code style), or rely only on indentation?
2. **Cascaded-out options**: When cascade is ON and options are filtered out — hide them entirely, or show them in a muted disabled state at the bottom? Hiding is cleaner; showing provides context.
3. **Chip overflow**: When many items are selected (5+), should chips wrap to multiple lines, or collapse into a count chip (`5 selected`) with a popover to see/manage all?
4. **Panel animation**: Slide-in from left (default), or instant expand? What easing curve for the slide?
5. **Section ordering**: Should users be able to drag-reorder filter sections, or is the fixed order sufficient?
6. **Saved filter presets**: Should there be a "Save as preset" option to name and recall filter combinations? (Future consideration — not required for v1.)
