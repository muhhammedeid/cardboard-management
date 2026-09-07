frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Cardboard Top Suppliers"] = {
	method: "cardboard_management.cardboard_management.dashboard_chart_source.cardboard_top_suppliers.cardboard_top_suppliers.get",
	filters: [],
};
