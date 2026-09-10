(function () {
	"use strict";

	const OPERATIONAL_DOCTYPES = new Set([
		"Cardboard Supply",
		"Quick Expense",
		"Cardboard Supplier Payment",
		"Cardboard Dashboard Settings",
		"Supplier",
		"Payment Entry",
	]);
	const CURRENCY_NORMALIZED_DOCTYPES = new Set([
		"Cardboard Supply",
		"Quick Expense",
		"Cardboard Supplier Payment",
	]);
	const OPERATIONAL_CURRENCY_REPORTS = new Set([
		"Stock Balance",
		"Accounts Payable",
		"Purchase Register",
	]);
	const PAYMENT_DOCTYPE = "Cardboard Supplier Payment";
	const PAYMENT_SUBMIT_LABEL = __("Save and Submit Payment");
	const SURFACE_CLASS = "cardboard-management-surface";
	const RTL_CLASS = "cardboard-management-rtl";
	const MALFORMED_EGP_SYMBOL = "£ or ج.م";
	const OPERATIONAL_EGP_SYMBOL = "ج.م";
	let registered = false;
	let workspace_currency_observer = null;

	function is_operational_route(route) {
		if (!Array.isArray(route) || route.length < 2) {
			return false;
		}

		const view = route[0];
		const target = route[1];
		if (view === "Workspaces" && target === "Cardboard Management") {
			return true;
		}

		return (view === "Form" || view === "List") && OPERATIONAL_DOCTYPES.has(target)
			|| (view === "Page" && target === "inventory-operational-view");
	}

	function is_workspace_route(route) {
		return Array.isArray(route) && route[0] === "Workspaces" && route[1] === "Cardboard Management";
	}

	function is_rtl() {
		if (window.frappe?.utils?.is_rtl) {
			return Boolean(window.frappe.utils.is_rtl());
		}

		return (
			window.frappe?.boot?.lang === "ar" ||
			document.documentElement.getAttribute("dir") === "rtl"
		);
	}

	function normalize_currency_value(value) {
		return typeof value === "string"
			? value.replaceAll(MALFORMED_EGP_SYMBOL, OPERATIONAL_EGP_SYMBOL)
			: value;
	}

	// Workspace Number Cards are not form controls. Retain the original narrowly
	// scoped text repair only for their asynchronous widget output.
	function normalize_workspace_currency_text(root = document.body) {
		if (!document.body?.classList.contains(SURFACE_CLASS) || !root) {
			return;
		}
		const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
		while (walker.nextNode()) {
			walker.currentNode.nodeValue = normalize_currency_value(walker.currentNode.nodeValue);
		}
	}

	// Frappe renders readonly Currency form fields through BaseInput.set_disp_area:
	// frappe.format -> frappe.form.formatters.Currency -> format_currency. Install
	// a DocField formatter only on Cardboard forms, then delegate all numeric work
	// to Frappe's native Currency formatter and replace its exact malformed EGP
	// presentation token in the returned display string.
	function operational_currency_formatter(value, df, options, doc) {
		const currency = window.frappe.meta.get_field_currency(df, doc);
		const formatted = window.frappe.form.formatters.Currency(value, df, options, doc);
		if (currency !== "EGP") {
			return formatted;
		}
		return normalize_currency_value(formatted);
	}
	operational_currency_formatter.cardboard_currency_presentation = true;

	function install_operational_currency_formatter(frm) {
		if (!CURRENCY_NORMALIZED_DOCTYPES.has(frm.doctype)) {
			return;
		}

		Object.entries(frm.fields_dict).forEach(([fieldname, field]) => {
			const df = field.df;
			if (df.fieldtype !== "Currency" || df.formatter?.cardboard_currency_presentation) {
				return;
			}
			df.formatter = operational_currency_formatter;
			frm.refresh_field(fieldname);
		});
	}

	function install_operational_currency_formatters() {
		if (!window.frappe?.ui?.form?.on) {
			return;
		}
		CURRENCY_NORMALIZED_DOCTYPES.forEach((doctype) => {
			window.frappe.ui.form.on(doctype, {
				refresh(frm) {
					install_operational_currency_formatter(frm);
				},
			});
		});
	}

	// Query Reports render Currency cells (including total rows) through the
	// report's formatter, which delegates native numeric presentation through
	// default_formatter. Compose the report's own formatter after its settings
	// load; this preserves its styling and numbers, changing only the known EGP
	// display token on the approved operational reports.
	function install_operational_report_currency_formatter(report) {
		const report_name = report?.report_name;
		const settings = report?.report_settings;
		if (!OPERATIONAL_CURRENCY_REPORTS.has(report_name) || !settings) {
			return;
		}

		if (settings.formatter?.cardboard_report_currency_presentation) {
			return;
		}

		const native_formatter = settings.formatter;
		function formatter(value, row, column, data, default_formatter, filter) {
			const formatted = native_formatter
				? native_formatter(value, row, column, data, default_formatter, filter)
				: default_formatter(value, row, column, data, filter);
			return column?.fieldtype === "Currency" ? normalize_currency_value(formatted) : formatted;
		}
		formatter.cardboard_report_currency_presentation = true;
		settings.formatter = formatter;
	}

	// QueryReport loads its settings before refresh_report(). Hook that lifecycle
	// instead of observing rendered report DOM, so asynchronous result rows and
	// totals are formatted natively on every report refresh or re-run.
	function install_operational_report_currency_formatter_hook() {
		const prototype = window.frappe?.views?.QueryReport?.prototype;
		const get_report_settings = prototype?.get_report_settings;
		if (!get_report_settings || get_report_settings.cardboard_report_currency_presentation) {
			return;
		}

		function patched_get_report_settings(...args) {
			return Promise.resolve(get_report_settings.apply(this, args)).then((result) => {
				install_operational_report_currency_formatter(this);
				return result;
			});
		}
		patched_get_report_settings.cardboard_report_currency_presentation = true;
		prototype.get_report_settings = patched_get_report_settings;
	}

	function apply_route_scope(route) {
		const body = document.body;
		if (!body) {
			return;
		}

		const current_route = route || window.frappe?.get_route?.() || [];
		const operational = is_operational_route(current_route);
		body.classList.toggle(SURFACE_CLASS, operational);
		body.classList.toggle(RTL_CLASS, operational && is_rtl());

		if (!is_workspace_route(current_route)) {
			workspace_currency_observer?.disconnect();
			workspace_currency_observer = null;
			return;
		}

		requestAnimationFrame(() => normalize_workspace_currency_text());
		if (!workspace_currency_observer) {
			workspace_currency_observer = new MutationObserver((mutations) => {
				mutations.forEach((mutation) => {
					mutation.addedNodes.forEach(normalize_workspace_currency_text);
				});
			});
			workspace_currency_observer.observe(body, { childList: true, subtree: true });
		}
	}

	// P03-R02: relabel the native form primary action for the supplier-payment
	// wrapper only. The click handler stays the native save/submit flow; no
	// custom accounting logic runs client-side.
	function install_payment_primary_action() {
		if (!window.frappe?.ui?.form?.on) {
			return;
		}
		window.frappe.ui.form.on(PAYMENT_DOCTYPE, {
			refresh(frm) {
				if (frm.doc.docstatus !== 0) {
					return;
				}
				frm.page.set_primary_action(PAYMENT_SUBMIT_LABEL, () => {
					frm.savesubmit();
				});
			},
		});
	}

	function register() {
		if (registered || !window.frappe) {
			return;
		}

		registered = true;
		install_operational_currency_formatters();
		install_operational_report_currency_formatter_hook();
		install_payment_primary_action();
		apply_route_scope();
		window.frappe.router?.on?.("change", apply_route_scope);
	}

	function schedule_register() {
		if (window.frappe) {
			register();
		} else {
			window.addEventListener("load", register, { once: true });
		}
	}

	window.cardboard_management_ux = Object.freeze({
		apply_route_scope,
		is_operational_route,
		is_rtl,
		install_operational_currency_formatter,
		install_operational_report_currency_formatter,
		install_operational_report_currency_formatter_hook,
	});

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", schedule_register, { once: true });
		window.addEventListener("load", register, { once: true });
	} else {
		schedule_register();
	}
})();
