# Cardboard Design System — P04-W01

## Approved sources

- P04-W00 Product UX Architecture & Screen Map governs information architecture, operational language, RTL behavior, responsiveness, and the frozen-backend boundary.
- `industrial_tactile_rtl/DESIGN.md` governs the Industrial Tactile RTL visual language.
- Golden-screen mapping: `_1` Operational Home, `_2` New Supply, `_3` Supplies List, `_4` Inventory. They are visual references only; their fictional values, device state, remote media, Tailwind CDN, and prototype scripts are not production dependencies.
- The Cardboard Management logo remains the approved product branding reference. Do not redraw it in product code.

## Foundation assets

- `public/css/cardboard_ui.css`: scoped `.cm-app` semantic tokens and responsive component styling.
- `public/js/cardboard_ui.js`: DOM-only UI primitives under `window.CardboardManagementUI`.
- `page/cardboard_ui_foundation/`: direct, development-only component review route; it is intentionally absent from product navigation.

## Visual tokens

| Role | Token/value |
|---|---|
| Primary operational teal | `--cm-color-primary: #1E3A40` |
| Deep primary | `--cm-color-primary-strong: #06242A` |
| Kraft action | `--cm-color-operational-accent: #D97706` |
| Precision teal | `--cm-color-precision: #0D9488` |
| Canvas/surface | `#F8FAFC` / `#FFFFFF` |
| Borders | `#E2E8F0` / `#CBD5E1` |
| Text | `#0F172A`, `#475569`, `#94A3B8` |

Use semantic tokens, not copied literal component colors. The CSS architecture is token-ready for a future dark theme; P04-W01 does not add a dark theme.

## Typography and layout

Arabic-first stack: `Noto Sans Arabic`, `Noto Sans`, Tahoma, Arial, sans-serif. Font delivery is deliberately local/system fallback only: no Google Fonts runtime dependency is added. Page title is 28/36 desktop and 22/30 mobile; compact review section headings are 18/26; KPI value is 36/44. Spacing follows 4, 8, 12, 16, 20, 24, 32, 40, 48, 64 px. Controls use 8 px radius, cards 12 px, panels 16 px. Surfaces use hairline borders and restrained elevation.

## RTL and value formatting

### Numbers and codes

The app root is `.cm-app[dir="rtl"]`. **No frontend business calculations** are permitted. Arabic is RTL; numbers, quantities, currency, percentages, and English codes use the `formatCurrency()`/`formatQuantity()`/`formatCode()` text formatters and the `createBidiValue()`/`renderBidiValue()` DOM renderer. Frappe alignment markup is normalized in a detached element, then the final plain value is assigned with `textContent` inside one `<bdi dir="ltr">` node. Callers never interpolate formatter output into HTML. No business totals, financial rounding, stock, supplier state, or report aggregate is calculated in the frontend.

## Golden reference calibration

The implemented shell is calibrated to the approved Stitch proportions: `280px` desktop right rail, `80px` tablet rail, `64px` top bar, `24px` desktop gutters, `16px` mobile gutters, `768px` mobile breakpoint, and `1600px` maximum content width. Desktop dense controls use `36px` visual height; mobile controls retain `44px` minimum touch targets. The review route uses `18/26px` section headings, `12/18px` supporting labels, `12px` section gaps, intrinsic-height cards, compact tables, `11px` status badges, and content-sized empty states. The shell grid explicitly uses LTR column ordering so the RTL rail remains physically on the right while its contents remain RTL.
## Shell and components

`mountAppShell()` provides the right RTL rail, top bar, quick-action entry point, responsive navigation contract, and page-frame slot. `createPageFrame()` provides title, subtitle, breadcrumb, context chip, actions, and body slots. The component system includes button variants, inputs, calculated fields, KPI/summary/data/record cards, status badges, filters, table/card transformations, pagination, tabs, dialog/drawer patterns, empty/error/permission/loading states, and scale-state visual primitives.

The global quick action exposes only presentation/action slots for توريدة جديدة, بيع جديد, دفعة مورد, and مصروف جديد. It does not create records in W01.

## Status vocabulary

- مسودة — draft
- معتمد — submitted
- ملغي — cancelled
- مدفوع — paid
- مدفوع جزئيًا — partly paid
- غير مدفوع — unpaid

All badges include text and a dot/shape treatment; color is never the only signal.

## Responsive and accessibility baseline

Desktop is `>=1024px`, tablet `768–1023px`, and mobile `<768px`. Desktop uses the 280 px right rail; tablet collapses it to an 80 px icon rail; mobile uses a drawer pattern and mobile action bar. Tables are hidden in favor of record cards at mobile sizes. Focus states, persistent labels, 44 px controls, dialog/drawer keyboard dismissal, semantic disabled/read-only states, and reduced-motion behavior are baseline requirements.

## Forbidden patterns

- Tailwind CDN: forbidden.
- Material Symbols CDN: forbidden.
- Google Fonts runtime loading: forbidden.
- Remote prototype images: forbidden.
- React, Vue, SPA framework, or new UI package: forbidden.
- Unscoped ERPNext/Frappe global restyling: forbidden.
- Frontend business calculations or deferred grouped report aggregates: forbidden.
- ERPNext/Frappe core, backend, permission, accounting, stock, or schema changes: forbidden.

## Implementation note

Later P04 packages consume this foundation without redesigning navigation, terminology, semantic tokens, responsive strategy, or backend contracts. The production visual gate remains user-owned.
