frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Cardboard Purchases by Type"] = {
	method: "cardboard_management.cardboard_management.dashboard_chart_source.cardboard_purchases_by_type.cardboard_purchases_by_type.get",
	filters: [],
};
