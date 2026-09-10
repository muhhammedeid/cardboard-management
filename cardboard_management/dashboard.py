import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, get_last_day, getdate, nowdate

from cardboard_management.inventory import get_inventory_context

SUPPLY_METRICS = {
	"today_supply_weight": ("net_weight", "today"),
	"today_purchase_amount": ("total_amount", "today"),
	"month_purchased_weight": ("net_weight", "month"),
	"month_purchase_cost": ("total_amount", "month"),
}
EXPENSE_METRICS = {
	"today_expenses": "today",
	"month_expenses": "month",
}
PAYMENT_METRICS = {
	"today_supplier_payments": "today",
	"month_supplier_payments": "month",
}


@frappe.whitelist()
def today_supplies_weight(filters=None):
	return _number_card("today_supply_weight", "Float", ["List", "Cardboard Supply"])


@frappe.whitelist()
def today_purchase_amount(filters=None):
	return _number_card("today_purchase_amount", "Currency", ["List", "Cardboard Supply"])


@frappe.whitelist()
def today_supplier_payments(filters=None):
	return _number_card("today_supplier_payments", "Currency", ["List", "Payment Entry"])


@frappe.whitelist()
def today_expenses(filters=None):
	return _number_card("today_expenses", "Currency", ["List", "Quick Expense"])


@frappe.whitelist()
def current_stock_weight(filters=None):
	return _number_card("current_stock_weight", "Float", ["query-report", "Stock Balance"])


@frappe.whitelist()
def supplier_outstanding(filters=None):
	return _number_card("supplier_outstanding", "Currency", ["query-report", "Accounts Payable"])


@frappe.whitelist()
def this_month_purchased_weight(filters=None):
	return _number_card("month_purchased_weight", "Float", ["List", "Cardboard Supply"])


@frappe.whitelist()
def this_month_purchase_cost(filters=None):
	return _number_card("month_purchase_cost", "Currency", ["List", "Cardboard Supply"])


@frappe.whitelist()
def this_month_expenses(filters=None):
	return _number_card("month_expenses", "Currency", ["List", "Quick Expense"])


@frappe.whitelist()
def this_month_paid_to_suppliers(filters=None):
	return _number_card("month_supplier_payments", "Currency", ["List", "Payment Entry"])



def _require_dashboard_access():
	frappe.has_permission("Cardboard Supply", "read", throw=True)


def _number_card(metric, fieldtype, route):
	_require_dashboard_access()
	settings = get_dashboard_settings()
	payload = {
		"value": get_metric_value(metric),
		"fieldtype": fieldtype,
		"precision": 3 if fieldtype == "Float" else 2,
		"route": route,
	}
	if fieldtype == "Currency":
		payload["options"] = frappe.get_cached_value("Company", settings.company, "default_currency")
	return payload


def get_dashboard_settings():
	return get_inventory_context()


def get_metric_value(metric, reference_date=None):
	settings = get_dashboard_settings()
	reference_date = getdate(reference_date or nowdate())
	if metric == "current_stock_weight":
		return _get_current_stock(settings.company, settings.warehouse, settings.item_groups)
	if metric == "supplier_outstanding":
		return _get_supplier_outstanding(
			settings.company, settings.warehouse, settings.item_groups, reference_date
		)

	from_date, to_date = _get_period(reference_date, _metric_period(metric))
	if metric in SUPPLY_METRICS:
		return _sum_supplies(
			SUPPLY_METRICS[metric][0],
			settings.company,
			settings.warehouse,
			settings.item_groups,
			from_date,
			to_date,
		)
	if metric in EXPENSE_METRICS:
		return _sum_expenses(settings.company, from_date, to_date)
	if metric in PAYMENT_METRICS:
		return _sum_supplier_payments(
			settings.company,
			settings.warehouse,
			settings.item_groups,
			from_date,
			to_date,
		)
	frappe.throw(_("Unknown dashboard metric: {0}").format(metric))


def get_chart_data(chart, reference_date=None):
	_require_dashboard_access()
	settings = get_dashboard_settings()
	reference_date = getdate(reference_date or nowdate())
	if chart == "daily_supplied_weight":
		return _daily_supplied_weight(
			settings.company, settings.warehouse, settings.item_groups, reference_date
		)
	if chart == "purchases_by_type":
		return _purchases_by_type(
			settings.company,
			settings.warehouse,
			settings.item_groups,
			get_first_day(reference_date),
			get_last_day(reference_date),
		)
	if chart == "top_suppliers":
		return _top_suppliers(
			settings.company,
			settings.warehouse,
			settings.item_groups,
			get_first_day(reference_date),
			get_last_day(reference_date),
		)
	if chart == "supplier_outstanding":
		return _supplier_outstanding_by_party(
			settings.company, settings.warehouse, settings.item_groups, reference_date
		)
	frappe.throw(_("Unknown dashboard chart: {0}").format(chart))


def _metric_period(metric):
	if metric in SUPPLY_METRICS:
		return SUPPLY_METRICS[metric][1]
	if metric in EXPENSE_METRICS:
		return EXPENSE_METRICS[metric]
	if metric in PAYMENT_METRICS:
		return PAYMENT_METRICS[metric]
	frappe.throw(_("Unknown dashboard metric: {0}").format(metric))


def _get_period(reference_date, period):
	if period == "today":
		return reference_date, reference_date
	return get_first_day(reference_date), get_last_day(reference_date)


def _item_group_placeholders(item_groups):
	return ", ".join(["%s"] * len(item_groups))


def _sum_supplies(fieldname, company, warehouse, item_groups, from_date, to_date):
	placeholders = _item_group_placeholders(item_groups)
	return flt(
		frappe.db.sql(
			f"""select coalesce(sum(cs.`{fieldname}`), 0)
			from `tabCardboard Supply` cs
			inner join `tabWarehouse` warehouse on warehouse.name = cs.warehouse
			inner join `tabItem` item on item.name = cs.item
			where cs.docstatus = 1
				and cs.posting_date between %s and %s
				and cs.warehouse = %s
				and warehouse.company = %s
				and item.item_group in ({placeholders})""",  # nosemgrep: fieldname comes from SUPPLY_METRICS
			(from_date, to_date, warehouse, company, *item_groups),
		)[0][0]
	)


def _sum_expenses(company, from_date, to_date):
	return flt(
		frappe.db.sql(
			"""select coalesce(sum(amount), 0)
			from `tabQuick Expense`
			where docstatus = 1
				and posting_date between %s and %s
				and company = %s""",
			(from_date, to_date, company),
		)[0][0]
	)


def _sum_supplier_payments(company, warehouse, item_groups, from_date, to_date):
	placeholders = _item_group_placeholders(item_groups)
	return flt(
		frappe.db.sql(
			f"""select coalesce(sum(reference.allocated_amount), 0)
			from `tabPayment Entry` payment
			inner join `tabPayment Entry Reference` reference
				on reference.parent = payment.name
				and reference.parenttype = 'Payment Entry'
				and reference.reference_doctype = 'Purchase Invoice'
			inner join `tabPurchase Invoice` invoice
				on invoice.name = reference.reference_name
				and invoice.docstatus = 1
				and coalesce(invoice.custom_cardboard_supply, '') != ''
			inner join `tabCardboard Supply` supply
				on supply.name = invoice.custom_cardboard_supply
			inner join `tabItem` item on item.name = supply.item
			where payment.docstatus = 1
				and payment.payment_type = 'Pay'
				and payment.party_type = 'Supplier'
				and payment.company = %s
				and payment.posting_date between %s and %s
				and supply.warehouse = %s
				and item.item_group in ({placeholders})""",
			(company, from_date, to_date, warehouse, *item_groups),
		)[0][0]
	)


def _get_current_stock(company, warehouse, item_groups):
	placeholders = _item_group_placeholders(item_groups)
	return flt(
		frappe.db.sql(
			f"""select coalesce(sum(bin.actual_qty), 0)
			from `tabBin` bin
			inner join `tabWarehouse` warehouse
				on warehouse.name = bin.warehouse
				and warehouse.company = %s
				and warehouse.name = %s
				and warehouse.is_group = 0
				and warehouse.disabled = 0
			inner join `tabItem` item
				on item.name = bin.item_code
				and item.is_stock_item = 1
				and item.disabled = 0
			where item.item_group in ({placeholders})""",
			(company, warehouse, *item_groups),
		)[0][0]
	)


def _get_supplier_outstanding(company, warehouse, item_groups, report_date):
	return sum(
		row.outstanding
		for row in _supplier_outstanding_rows(company, warehouse, item_groups, report_date, limit=None)
	)


def _supplier_outstanding_rows(company, warehouse, item_groups, report_date, limit=10):
	placeholders = _item_group_placeholders(item_groups)
	limit_clause = "limit 10" if limit else ""
	return frappe.db.sql(
		f"""select ple.party, sum(ple.amount) as outstanding
		from `tabPayment Ledger Entry` ple
		inner join `tabPurchase Invoice` invoice
			on invoice.name = ple.voucher_no
			and ple.voucher_type = 'Purchase Invoice'
			and invoice.docstatus = 1
			and coalesce(invoice.custom_cardboard_supply, '') != ''
		inner join `tabCardboard Supply` supply
			on supply.name = invoice.custom_cardboard_supply
		inner join `tabItem` item on item.name = supply.item
		where ple.delinked = 0
			and ple.company = %s
			and ple.account_type = 'Payable'
			and ple.party_type = 'Supplier'
			and supply.warehouse = %s
			and item.item_group in ({placeholders})
			and ple.posting_date <= %s
		group by ple.party
		having sum(ple.amount) > 0
		order by outstanding desc
		{limit_clause}""",  # nosemgrep: limit clause is selected internally
		(company, warehouse, *item_groups, report_date),
		as_dict=True,
	)


def _daily_supplied_weight(company, warehouse, item_groups, to_date):
	from_date = add_days(to_date, -29)
	placeholders = _item_group_placeholders(item_groups)
	rows = frappe.db.sql(
		f"""select cs.posting_date, sum(cs.net_weight) as value
		from `tabCardboard Supply` cs
		inner join `tabWarehouse` warehouse on warehouse.name = cs.warehouse
		inner join `tabItem` item on item.name = cs.item
		where cs.docstatus = 1
			and cs.posting_date between %s and %s
			and cs.warehouse = %s
			and warehouse.company = %s
			and item.item_group in ({placeholders})
		group by cs.posting_date
		order by cs.posting_date""",
		(from_date, to_date, warehouse, company, *item_groups),
		as_dict=True,
	)
	values_by_date = {str(row.posting_date): flt(row.value) for row in rows}
	labels = [str(add_days(from_date, offset)) for offset in range(30)]
	return _chart(labels, [values_by_date.get(label, 0) for label in labels], _("Supplied Weight"))


def _purchases_by_type(company, warehouse, item_groups, from_date, to_date):
	placeholders = _item_group_placeholders(item_groups)
	rows = frappe.db.sql(
		f"""select cs.item, sum(cs.net_weight) as value
		from `tabCardboard Supply` cs
		inner join `tabWarehouse` warehouse
			on warehouse.name = cs.warehouse and warehouse.company = %s
		inner join `tabItem` item on item.name = cs.item
		where cs.docstatus = 1
			and cs.warehouse = %s
			and cs.posting_date between %s and %s
			and item.item_group in ({placeholders})
		group by cs.item
		order by value desc""",
		(company, warehouse, from_date, to_date, *item_groups),
		as_dict=True,
	)
	return _rows_to_chart(rows, "item", _("Purchased Weight"))


def _top_suppliers(company, warehouse, item_groups, from_date, to_date):
	placeholders = _item_group_placeholders(item_groups)
	rows = frappe.db.sql(
		f"""select cs.supplier, sum(cs.net_weight) as value
		from `tabCardboard Supply` cs
		inner join `tabWarehouse` warehouse
			on warehouse.name = cs.warehouse and warehouse.company = %s
		inner join `tabItem` item on item.name = cs.item
		where cs.docstatus = 1
			and cs.warehouse = %s
			and cs.posting_date between %s and %s
			and item.item_group in ({placeholders})
		group by cs.supplier
		order by value desc
		limit 10""",
		(company, warehouse, from_date, to_date, *item_groups),
		as_dict=True,
	)
	return _rows_to_chart(rows, "supplier", _("Purchased Weight"))


def _supplier_outstanding_by_party(company, warehouse, item_groups, report_date):
	return _rows_to_chart(
		_supplier_outstanding_rows(company, warehouse, item_groups, report_date),
		"party",
		_("Outstanding Amount"),
	)


def _rows_to_chart(rows, label_field, dataset_name):
	return _chart(
		[row.get(label_field) for row in rows],
		[flt(row.value if "value" in row else row.outstanding) for row in rows],
		dataset_name,
	)


def _chart(labels, values, dataset_name):
	return {"labels": labels, "datasets": [{"name": dataset_name, "values": values}]}
