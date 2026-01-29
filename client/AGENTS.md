This website is a broader part of : website for banking like professional setup which deals with Risk management for non financial risk: the website does enhance monitoring, reporting, ai agent chat application thorough Models are based on LLMs and Graph algorithms, there is agentic chat to ask about query, visualize.

All website is in light mode, full screen, no dark mode, no vertical scroll. 

Libraries to use:
Components: 
Shadcn: https://ui.shadcn.com/llms.txt This URL have all the ref links for shadcn components.
Icons: Lucide-react
State-management: Zustand: https://zustand.docs.pmnd.rs/getting-started/introduction
Styling: Tailwind

Backgrounds

primary: #ffffff — ubs-white (main background)

secondary: #f9f9f7 — ubs-neutral10 (cards, sections)

tertiary: #f4f3ee — ubs-neutral20 (subtle highlights)

Text

primary: #1c1c1c — ubs-cod (headings)

secondary: #5a5d5c — ubs-neutral70 (body text)

muted: #8e8d83 — ubs-neutral50 (labels, captions)

Accent / Brand

primary: #e60000 — ubs-red (primary CTA, brand)

hover: #da0000 — ubs-red-web (hover states)

pressed: #bd000c — ubs-bordeaux1 (pressed states)

Status / Feedback

success: #498100 — ubs-metric-green

error: #c81219 — ubs-metric-red

warning: #e5b01c — ubs-curry

info: #0097cc — ubs-lagoon50

Borders & Dividers

light: #e0dfd7 — ubs-neutral25

default: #cccabc — ubs-neutral30

, design principle: Design Principle:

Sharp, Functional, Information-First

This spec follows the design language seen in modern agentic chat UIs (like Cursor, Windsurf, Claude artifacts panel), trading terminals (TradingView, Bloomberg), and enterprise dashboards. The goal: maximum information density without sacrificing readability.

Type Scale (Major Second Ratio: 1.125)
| Token        | Size   | Line Height | Weight | Use Case                          |

|--------------|--------|-------------|--------|-----------------------------------|

| --text-xs  | 10px   | 14px        | 400    | Timestamps, tertiary labels       |

| --text-sm  | 11px   | 16px        | 400    | Captions, metadata                |

| --text-base| 12px   | 18px        | 400    | Body text, input fields           |

| --text-md  | 13px   | 20px        | 500    | Primary labels, list items        |

| --text-lg  | 14px   | 20px        | 500    | Section headers, emphasis         |

| --text-xl  | 16px   | 24px        | 600    | Panel titles                      |

| --text-2xl | 18px   | 26px        | 600    | Page headers                      |

| --text-3xl | 24px   | 32px        | 700    | Hero numbers, KPIs  

Typography Rules
Base size: 12-13px (not 16px) for dense interfaces

Line height: 1.4-1.5x font size for body, 1.2-1.3x for headings

Letter spacing: 0 to -0.01em for body, -0.02em for large headings

Monospace for data: Numbers, code, timestamps always in mono

2. SPACING SYSTEM
Base Unit: 4px
| Token       | Value | Use Case                                    |

|-------------|-------|---------------------------------------------|

| --space-1 | 2px   | Inline icon-text gap, micro adjustments     |

| --space-2 | 4px   | Tight padding, related element gap          |

| --space-3 | 6px   | Input padding (vertical)                    |

| --space-4 | 8px   | Standard component padding                  |

| --space-5 | 12px  | Section gaps, card padding                  |

| --space-6 | 16px  | Panel padding, larger gaps                  |

| --space-7 | 20px  | Major section breaks                        |

| --space-8 | 24px  | Page margins, large panels                  |

| --space-9 | 32px  | Major layout spacing                        |

| --space-10| 48px  | Page-level spacing                          |

Density Guidelines
Compact lists: 4-6px vertical padding per item

Tables: 8px horizontal, 6px vertical cell padding

Cards: 12px internal padding

Panels: 16px padding

3. BORDER RADIUS
Radius Scale (Sharp, Not Soft)
| Token         | Value | Use Case                                  |

|---------------|-------|-------------------------------------------|

| --radius-none | 0px   | Tables, some panels, data grids         |

| --radius-xs | 2px   | Default - Buttons, inputs, badges     |

| --radius-sm | 3px   | Tags, chips, small controls               |

| --radius-md | 4px   | Cards, panels, modals                     |

| --radius-lg | 6px   | Larger containers, rarely used            |

| --radius-pill| 9999px| Toggle switches, status dots             |

## Responsive Design Guide

### Breakpoints

| Breakpoint | Width | Target Devices |
|------------|-------|----------------|
| Default | 0-639px | Mobile phones |
| sm | 640px+ | Large phones, small tablets |
| md | 768px+ | Tablets |
| lg | 1024px+ | Laptops, small desktops |
| xl | 1280px+ | Desktops |
| 2xl | 1536px+ | Large desktops, ultrawide |

### Standard Responsive Patterns

**Container Max-Widths:**
```
max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px]
```

**Horizontal Padding:**
```
px-3 sm:px-4
```
- 12px on mobile (px-3)
- 16px on tablet and above (sm:px-4)

**Grid Columns Pattern:**
```
grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5
```
- 1 column on mobile
- 2 columns on small tablets (sm)
- 3 columns on laptops (lg)
- 4 columns on desktops (xl)
- 5 columns on large desktops (2xl)

### Component Responsive Rules

**Navigation:**
- Desktop navigation visible at `md` breakpoint and above
- Mobile hamburger menu displayed below `md` breakpoint
- Use `hidden md:flex` for desktop nav items
- Use `md:hidden` for mobile menu toggle

**Sidebars:**
- Drawer/overlay on mobile (below lg)
- Fixed position on `lg` and above
- Wider on `xl` and above: `w-64 xl:w-72`
- Example: `fixed lg:static w-64 xl:w-72`

**Cards:**
- Full width on mobile
- Grid layout on larger screens
- Example: `w-full sm:w-auto` or use grid patterns above

**Tables:**
- Wrap tables in horizontal scroll container on small screens
- Example wrapper: `overflow-x-auto` on parent container
- Consider card-based layout for mobile as alternative

### Large Screen Considerations (Priority)

These are critical for ensuring the application looks good on large monitors:

1. **Always use responsive max-widths that scale up**
   - Never use fixed max-widths that leave empty space on large screens
   - Use: `max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px]`

2. **Grids should add more columns on xl/2xl**
   - Don't stop at 3 columns; add 4-5 columns on larger screens
   - Use: `lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5`

3. **Sidebars can be wider on large screens**
   - Increase sidebar width at xl breakpoint
   - Use: `w-64 xl:w-72` or `w-64 xl:w-80`

4. **Content should utilize available space**
   - Avoid large empty margins on wide screens
   - Consider multi-column layouts for content areas
   - Data tables can show more columns on larger screens

### Mobile Considerations

1. **Touch Targets:**
   - Minimum touch target size: 44px × 44px
   - Use: `min-h-[44px] min-w-[44px]` for interactive elements

2. **Reduced Padding on Mobile:**
   - Use smaller padding values on mobile
   - Example: `p-2 sm:p-3 md:p-4`

3. **Stack Layouts Vertically:**
   - Convert horizontal layouts to vertical on mobile
   - Use: `flex-col sm:flex-row`

4. **Hide Non-Essential Elements:**
   - Hide secondary information on mobile
   - Use: `hidden sm:block` for non-critical elements

### Standard Classes to Use

**Layout Containers:**
```
// Page container
mx-auto max-w-6xl xl:max-w-7xl 2xl:max-w-[1600px] px-3 sm:px-4

// Section container
w-full max-w-full lg:max-w-[calc(100%-16rem)] xl:max-w-[calc(100%-18rem)]
```

**Responsive Grids:**
```
// Standard content grid
grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3 sm:gap-4

// Dashboard cards grid
grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4
```

**Responsive Flexbox:**
```
// Stack on mobile, row on larger
flex flex-col sm:flex-row gap-2 sm:gap-4

// Justify content responsively
flex flex-col sm:flex-row sm:items-center sm:justify-between
```

**Responsive Spacing:**
```
// Padding
p-2 sm:p-3 md:p-4
px-3 sm:px-4 md:px-6
py-2 sm:py-3 md:py-4

// Margins
mt-4 sm:mt-6 md:mt-8
mb-3 sm:mb-4 md:mb-6

// Gaps
gap-2 sm:gap-3 md:gap-4
```

**Responsive Typography:**
```
// Headings
text-lg sm:text-xl md:text-2xl
text-base sm:text-lg

// Body text maintains base size but can adjust
text-sm sm:text-base
```

**Responsive Visibility:**
```
// Show only on mobile
block sm:hidden

// Hide on mobile, show on tablet+
hidden sm:block

// Hide on mobile/tablet, show on desktop+
hidden lg:block

// Show on mobile/tablet, hide on desktop+
lg:hidden
```

**Sidebar Patterns:**
```
// Responsive sidebar
w-64 xl:w-72 fixed lg:static h-full lg:h-auto

// Main content with sidebar offset
ml-0 lg:ml-64 xl:ml-72
```

**Interactive Elements:**
```
// Touch-friendly buttons
min-h-[44px] px-4 py-2 sm:py-1.5

// Touch-friendly list items
py-3 sm:py-2 px-3 sm:px-4
```