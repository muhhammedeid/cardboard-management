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
	const PAYMENT_DOCTYPE = "Cardboard Supplier Payment";
	const PAYMENT_SUBMIT_LABEL = __("Save and Submit Payment");
	const SURFACE_CLASS = "cardboard-management-surface";
	const RTL_CLASS = "cardboard-management-rtl";
	const MALFORMED_EGP_SYMBOL = "£ or ج.م";
	const OPERATIONAL_EGP_SYMBOL = "ج.م";
	let registered = false;
	let currency_observer = null;

	function is_operational_route(route) {
		if (!Array.isArray(route) || route.length < 2) {
			return false;
		}

		const view = route[0];
		const target = route[1];
		if (view === "Workspaces" && target === "Cardboard Management") {
			return true;
		}

		return (view === "Form" || view === "List") && OPERATIONAL_DOCTYPES.has(target);
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

	function normalize_operational_currency_text(root = document.body) {
		const body = document.body;
		if (!body?.classList.contains(SURFACE_CLASS) || !root) {
			return;
		}
		const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
		const text_nodes = [];
		while (walker.nextNode()) {
			text_nodes.push(walker.currentNode);
		}
		text_nodes.forEach((node) => {
			if (node.nodeValue.includes(MALFORMED_EGP_SYMBOL)) {
				node.nodeValue = node.nodeValue.replaceAll(MALFORMED_EGP_SYMBOL, OPERATIONAL_EGP_SYMBOL);
			}
		});
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
		if (!operational) {
			currency_observer?.disconnect();
			currency_observer = null;
			return;
		}
		normalize_operational_currency_text();
		if (!currency_observer) {
			currency_observer = new MutationObserver((mutations) => {
				mutations.forEach((mutation) => mutation.addedNodes.forEach(normalize_operational_currency_text));
			});
			currency_observer.observe(body, { childList: true, subtree: true });
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
	});

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", schedule_register, { once: true });
		window.addEventListener("load", register, { once: true });
	} else {
		schedule_register();
	}
})();
