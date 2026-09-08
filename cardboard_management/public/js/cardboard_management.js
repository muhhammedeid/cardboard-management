(function () {
	"use strict";

	const OPERATIONAL_DOCTYPES = new Set([
		"Cardboard Supply",
		"Quick Expense",
		"Cardboard Dashboard Settings",
		"Supplier",
		"Payment Entry",
	]);
	const SURFACE_CLASS = "cardboard-management-surface";
	const RTL_CLASS = "cardboard-management-rtl";
	let registered = false;

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

	function apply_route_scope(route) {
		const body = document.body;
		if (!body) {
			return;
		}

		const current_route = route || window.frappe?.get_route?.() || [];
		const operational = is_operational_route(current_route);
		body.classList.toggle(SURFACE_CLASS, operational);
		body.classList.toggle(RTL_CLASS, operational && is_rtl());
	}

	function register() {
		if (registered || !window.frappe) {
			return;
		}

		registered = true;
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
