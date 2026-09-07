frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Cardboard Supplier Outstanding"] = {
	method: "cardboard_management.cardboard_management.dashboard_chart_source.cardboard_supplier_outstanding.cardboard_supplier_outstanding.get",
	filters: [],
};
