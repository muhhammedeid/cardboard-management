"""Database-free source contracts for the P04-W01 shared product UI foundation."""

from pathlib import Path
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
APP_ROOT = PACKAGE.parent
CSS = PACKAGE / "public" / "css" / "cardboard_ui.css"
JS = PACKAGE / "public" / "js" / "cardboard_ui.js"
PAGE = PACKAGE / "cardboard_management" / "page" / "cardboard_ui_foundation"
PAGE_JS = PAGE / "cardboard_ui_foundation.js"
RUNTIME_TEST = PACKAGE / "tests" / "cardboard_ui_foundation_runtime.test.js"
DOC = APP_ROOT / "docs" / "ui" / "cardboard-design-system.md"
HOOKS = PACKAGE / "hooks.py"


class TestCardboardUiFoundationSource(unittest.TestCase):
    def test_foundation_assets_and_review_page_are_shipped(self):
        self.assertTrue(CSS.is_file())
        self.assertTrue(JS.is_file())
        self.assertTrue((PAGE / "cardboard_ui_foundation.js").is_file())
        self.assertTrue((PAGE / "cardboard_ui_foundation.json").is_file())
        self.assertTrue(RUNTIME_TEST.is_file())
        self.assertTrue(DOC.is_file())

    def test_assets_are_registered_and_scoped_to_the_app(self):
        hooks = HOOKS.read_text(encoding="utf-8")
        css = CSS.read_text(encoding="utf-8")
        self.assertIn('/assets/cardboard_management/css/cardboard_ui.css', hooks)
        self.assertIn('/assets/cardboard_management/js/cardboard_ui.js', hooks)
        self.assertIn('.cm-app', css)
        self.assertNotIn('\n.btn {', css)
        self.assertNotIn('\n.form-control {', css)
        self.assertNotIn('tailwindcss.com', css)
        self.assertNotIn('@import url(', css)

    def test_tokens_cover_the_approved_visual_and_accessibility_contract(self):
        css = CSS.read_text(encoding="utf-8")
        for marker in (
            '--cm-color-primary: #1e3a40',
            '--cm-color-primary-strong: #06242a',
            '--cm-color-operational-accent: #d97706',
            '--cm-color-canvas: #f8fafc',
            '--cm-color-surface: #ffffff',
            '--cm-color-border: #e2e8f0',
            '--cm-status-approved-bg: #ecfdf5',
            '--cm-space-4: 1rem',
            '--cm-radius-control: 0.5rem',
            '--cm-shadow-overlay:',
            '--cm-focus-ring:',
            '--cm-breakpoint-tablet: 768px',
            '--cm-breakpoint-desktop: 1024px',
            'font-variant-numeric: tabular-nums',
            'unicode-bidi: isolate',
            '@media (prefers-reduced-motion: reduce)',
        ):
            self.assertIn(marker, css)

    def test_shared_component_contract_is_present_without_business_logic(self):
        css = CSS.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        for marker in (
            '.cm-app-shell', '.cm-nav-rail', '.cm-topbar', '.cm-page-frame',
            '.cm-page-header', '.cm-breadcrumb', '.cm-context-chip',
            '.cm-quick-action', '.cm-mobile-action-bar', '.cm-button--primary',
            '.cm-input', '.cm-field--calculated', '.cm-kpi-card', '.cm-status',
            '.cm-filter-bar', '.cm-data-table', '.cm-record-card', '.cm-tabs',
            '.cm-dialog', '.cm-drawer', '.cm-empty-state', '.cm-error-state',
            '.cm-skeleton', '.cm-permission-state', '.cm-scale-status',
        ):
            self.assertIn(marker, css)
        for marker in (
            'mountAppShell', 'createPageFrame', 'createQuickAction',
            'createDialog', 'createDrawer', 'formatCurrency', 'formatQuantity',
            'formatCode', 'CardboardManagementUI',
        ):
            self.assertIn(marker, js)
        self.assertNotIn('frappe.call(', js)
        self.assertNotIn('frappe.db.', js)
        self.assertNotIn('calculateTotal', js)

    def test_foundation_surface_exposes_app_shell_and_hides_desk_chrome(self):
        css = CSS.read_text(encoding="utf-8")
        page = PAGE_JS.read_text(encoding="utf-8")
        self.assertIn('mountAppShell(page.main[0]', page)
        self.assertIn('active: "home"', page)
        self.assertIn('body[data-route="Page/cardboard-ui-foundation"] .navbar', css)
        self.assertIn('body[data-route="Page/cardboard-ui-foundation"] .page-head', css)
        self.assertIn('.cm-foundation-review', css)

    def test_bidi_formatters_build_safe_dom_values(self):
        js = JS.read_text(encoding="utf-8")
        page = PAGE_JS.read_text(encoding="utf-8")
        for marker in (
            'document.createElement("bdi")',
            'setAttribute("dir", "ltr")',
            '.textContent =',
            'formatDisplayText',
            'normalizeDisplayText',
        ):
            self.assertIn(marker, js)
        self.assertIn('renderBidiValue', js)
        self.assertNotIn('return `<bdi', js)
        self.assertIn('ui.renderBidiValue', page)
        self.assertNotIn('replaceWith(ui.formatCurrency', page)
        self.assertNotIn('replaceWith(ui.formatQuantity', page)
        self.assertNotIn('replaceWith(ui.formatCode', page)
        self.assertNotIn('${ui.formatCurrency', page)
        self.assertNotIn('${ui.formatQuantity', page)
        self.assertNotIn('${ui.formatCode', page)

    def test_scale_status_and_review_density_are_compact(self):
        css = CSS.read_text(encoding="utf-8")
        for marker in (
            'justify-self:start',
            'width:max-content',
            '.cm-foundation-review .cm-empty-state',
        ):
            self.assertIn(marker, css)
    def test_compact_density_contract_preserves_mobile_touch_targets(self):
        css = CSS.read_text(encoding="utf-8")
        for marker in (
            'font-size: 14px; line-height: 1.45;',
            '.cm-page-frame { max-width:1600px; margin:auto; padding:var(--cm-space-5)',
            '.cm-page-title{margin:0;font-size:24px;line-height:32px',
            '.cm-card{padding:var(--cm-space-4)}',
            '.cm-kpi-card__value{font-size:32px;line-height:40px',
            '.cm-data-table th,.cm-data-table td{padding:var(--cm-space-2) var(--cm-space-3)',
            '.cm-nav-item { min-height:var(--cm-density-nav-row-height)',
            '.cm-button,.cm-icon-button { border:1px solid transparent; cursor:pointer; border-radius:var(--cm-radius-control); min-height:36px',
            '.cm-input,.cm-select,.cm-search-input,.cm-textarea { width:100%;min-height:38px',
            '.cm-status { display:inline-flex;align-items:center;gap:6px;width:max-content;padding:2px 8px',
            '.cm-empty-state,.cm-error-state,.cm-permission-state{min-height:0',
            '.cm-foundation-review { gap: 12px; }',
            '.cm-foundation-review .cm-kpi-card { min-height: 0; padding: 14px; }',
            '.cm-foundation-review .cm-data-table th,',
            '.cm-foundation-review .cm-scale-status { justify-self:start; width:max-content; max-width:100%; padding:2px 8px',
            '@media (max-width:767px)',
            '.cm-button,.cm-icon-button{min-height:44px}',
            '.cm-input,.cm-select,.cm-search-input{min-height:44px}',
        ):
            self.assertIn(marker, css)

        css = CSS.read_text(encoding="utf-8")
        for marker in (
            '--cm-density-nav-expanded-width: 232px',
            '--cm-density-nav-collapsed-width: 60px',
            '--cm-density-topbar-height: 52px',
            '--cm-breakpoint-tablet: 768px',
            'direction: ltr;',
            'border-left: 1px solid var(--cm-color-border);',
            'grid-template-columns:minmax(0,1fr) var(--cm-density-nav-expanded-width)',
            '.cm-foundation-review .cm-page-title { font-size: 18px',
            '.cm-foundation-review .cm-empty-state { min-height: 0',
            '.cm-foundation-review .cm-data-table th',
            '.cm-kpi-card { min-height: 0',
        ):
            self.assertIn(marker, css)

    def test_review_uses_one_text_to_dom_bidi_contract(self):
        js = JS.read_text(encoding="utf-8")
        page = PAGE_JS.read_text(encoding="utf-8")
        for marker in ('createBidiValue', 'renderBidiValue', 'textContent =', 'setAttribute("dir", "ltr")'):
            self.assertIn(marker, js)
        for marker in ('ui.renderBidiValue(body', 'ui.formatCurrency(5200', 'ui.formatQuantity(900', 'ui.formatCode("CARDBOARD-A"'):
            self.assertIn(marker, page)
        self.assertNotIn('replaceWith(ui.formatCurrency', page)
        self.assertNotIn('replaceWith(ui.formatQuantity', page)
        self.assertNotIn('replaceWith(ui.formatCode', page)
        self.assertNotIn('${ui.formatCurrency', page)
        self.assertNotIn('${ui.formatQuantity', page)
        self.assertNotIn('${ui.formatCode', page)

    def test_navigation_uses_one_canonical_source_and_right_drawer_contract(self):
        css = CSS.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        self.assertIn('const NAVIGATION = Object.freeze([', js)
        self.assertIn('function renderNavigation(active)', js)
        self.assertIn('function navigationMarkup(active)', js)
        self.assertIn('createNavigationDrawer', js)
        self.assertIn('data-cm-toggle-navigation', js)
        self.assertNotIn('data-cm-open-navigation', js)
        self.assertNotIn('data-cm-open-drawer', js)
        self.assertIn('data-cm-nav-group="primary"', js)
        self.assertIn('data-cm-nav-group="secondary"', js)
        self.assertIn('cm-overlay--navigation', js)
        self.assertIn('cm-overlay--drawer,.cm-overlay--navigation', css)
        self.assertIn('justify-content:flex-end', css)
        self.assertIn('@media (min-width:768px){.cm-overlay--navigation{display:none!important}}', css)
        self.assertIn('.cm-navigation-drawer{width:min(280px,100%);height:100%;overflow:auto}', css)

    def test_density_lock_does_not_use_css_zoom_or_root_scale(self):
        css = CSS.read_text(encoding="utf-8")
        self.assertNotIn('zoom:', css)
        self.assertNotIn('transform:scale(0.8)', css)
        self.assertNotIn('transform: scale(0.8)', css)

    def test_w01r5_uses_compact_desktop_density_tokens(self):
        css = CSS.read_text(encoding="utf-8")
        for marker in (
            '--cm-density-font-page-title:',
            '--cm-density-font-section:',
            '--cm-density-font-body:',
            '--cm-density-topbar-height:',
            '--cm-density-nav-expanded-width:',
            '--cm-density-nav-collapsed-width:',
            '--cm-density-nav-row-height:',
            '--cm-density-control-height:',
            '--cm-density-card-padding:',
            '--cm-density-section-gap:',
            '--cm-density-page-gutter:',
            '--cm-density-table-cell-y:',
            'grid-template-columns:minmax(0,1fr) var(--cm-density-nav-expanded-width)',
            'grid-template-columns:minmax(0,1fr) var(--cm-density-nav-collapsed-width)',
        ):
            self.assertIn(marker, css)

    def test_w01r5_navigation_is_one_stateful_shell_control(self):
        css = CSS.read_text(encoding="utf-8")
        js = JS.read_text(encoding="utf-8")
        page = PAGE_JS.read_text(encoding="utf-8")
        for marker in (
            'data-cm-toggle-navigation',
            'cm-navigation-collapsed',
            'data-cm-navigation-state',
            '.cm-app-shell.cm-navigation-collapsed',
            '.cm-navigation-expanded',
            '.cm-navigation-collapsed .cm-nav-rail',
            '.cm-navigation-collapsed .cm-nav-item__label',
            '@media (min-width:1024px)',
            'cm-overlay--navigation',
        ):
            self.assertIn(marker, css + js)
        self.assertNotIn('data-cm-open-navigation', js)
        self.assertNotIn('.cm-navigation-open .cm-nav-rail{display:none!important}', css)
        self.assertNotIn('createDrawer(page.main[0]', page)
        self.assertNotIn('data-demo-drawer', page)

    def test_navigation_visibility_contract_is_explicit(self):
        css = CSS.read_text(encoding="utf-8")
        self.assertIn('@media (max-width:1023px) and (min-width:768px)', css)
        self.assertIn('@media (max-width:767px)', css)
        self.assertIn('.cm-nav-rail{display:none}', css)
        self.assertIn('.cm-topbar__menu{display:inline-flex', css)
        self.assertIn('.cm-navigation-drawer', css)
        self.assertIn('@media (min-width:1024px)', css)
        self.assertIn('.cm-app-shell.cm-navigation-collapsed', css)

    def test_foundation_document_records_sources_and_forbidden_dependencies(self):
        document = DOC.read_text(encoding="utf-8")
        for marker in (
            'P04-W00', 'Industrial Tactile RTL', 'Noto Sans Arabic',
            'Tailwind CDN: forbidden', 'Material Symbols CDN: forbidden',
            'Numbers and codes', 'No frontend business calculations',
            'Golden reference calibration', '232px', '60px', '52px',
            'renderBidiValue', 'compact desktop density layer',
        ):
            self.assertIn(marker, document)
        self.assertNotIn('264 px right rail', document)
        self.assertNotIn('640–1023px', document)


if __name__ == '__main__':
    unittest.main()
