"""Database-free source contracts for the P04-W01 shared product UI foundation."""

from pathlib import Path
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
APP_ROOT = PACKAGE.parent
CSS = PACKAGE / "public" / "css" / "cardboard_ui.css"
JS = PACKAGE / "public" / "js" / "cardboard_ui.js"
PAGE = PACKAGE / "cardboard_management" / "page" / "cardboard_ui_foundation"
PAGE_JS = PAGE / "cardboard_ui_foundation.js"
DOC = APP_ROOT / "docs" / "ui" / "cardboard-design-system.md"
HOOKS = PACKAGE / "hooks.py"


class TestCardboardUiFoundationSource(unittest.TestCase):
    def test_foundation_assets_and_review_page_are_shipped(self):
        self.assertTrue(CSS.is_file())
        self.assertTrue(JS.is_file())
        self.assertTrue((PAGE / "cardboard_ui_foundation.js").is_file())
        self.assertTrue((PAGE / "cardboard_ui_foundation.json").is_file())
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
            '--cm-breakpoint-tablet: 640px',
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
        ):
            self.assertIn(marker, js)
        self.assertNotIn('return `<bdi', js)
        self.assertIn('replaceWith(ui.formatCurrency', page)
        self.assertIn('replaceWith(ui.formatQuantity', page)
        self.assertIn('replaceWith(ui.formatCode', page)
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
    def test_foundation_document_records_sources_and_forbidden_dependencies(self):
        document = DOC.read_text(encoding="utf-8")
        for marker in (
            'P04-W00', 'Industrial Tactile RTL', 'Noto Sans Arabic',
            'Tailwind CDN: forbidden', 'Material Symbols CDN: forbidden',
            'Numbers and codes', 'No frontend business calculations',
        ):
            self.assertIn(marker, document)


if __name__ == '__main__':
    unittest.main()
