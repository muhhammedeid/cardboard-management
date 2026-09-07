import frappe
from frappe.utils.dashboard import cache_source

from cardboard_management.dashboard import get_chart_data


@frappe.whitelist()
@cache_source
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	frappe.has_permission("Cardboard Supply", "read", throw=True)
	return get_chart_data("supplier_outstanding")
