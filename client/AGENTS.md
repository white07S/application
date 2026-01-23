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