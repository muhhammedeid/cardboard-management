frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Cardboard Daily Supplied Weight"] = {
	method: "cardboard_management.cardboard_management.dashboard_chart_source.cardboard_daily_supplied_weight.cardboard_daily_supplied_weight.get",
	filters: [],
};
