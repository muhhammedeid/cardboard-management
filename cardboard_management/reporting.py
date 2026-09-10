"""Normalized, installation-scoped operational reporting read services."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from frappe.utils.nestedset import get_descendants_of

from cardboard_management.inventory import get_inventory_context


STATUS_VALUES = {"submitted": 1, "draft": 0, "cancelled": 2}


def _require_reporting_access(*doctypes):
    for doctype in doctypes or ("Cardboard Supply",):
        frappe.has_permission(doctype, "read", throw=True)


def _date_range(from_date=None, to_date=None):
    today = getdate(nowdate())
    start = getdate(from_date or to_date or today)
    end = getdate(to_date or today if from_date else start)
    if start > end:
        frappe.throw(_("From Date cannot be after To Date"))
    if end > today:
        frappe.throw(_("To Date cannot be in the future"))
    return start, end


def _status(status=None):
    value = str(status or "submitted").strip().lower()
    if value not in (*STATUS_VALUES, "all"):
        frappe.throw(_("Invalid reporting status: {0}").format(frappe.bold(status)))
    return value


def _context(from_date=None, to_date=None, cardboard_item=None, supplier=None, status=None, required_doctypes=None):
    _require_reporting_access(*(required_doctypes or ("Cardboard Supply",)))
    context = get_inventory_context()
    start, end = _date_range(from_date, to_date)
    status_value = _status(status) if status is not None else None
    item_codes = {item.name for item in context["items"]}
    if cardboard_item and cardboard_item not in item_codes:
        frappe.throw(_("Cardboard item is outside the configured reporting scope"))
    if supplier and not frappe.db.exists("Supplier", supplier):
        frappe.throw(_("Supplier {0} does not exist").format(frappe.bold(supplier)))
    return frappe._dict(
        context=context,
        from_date=start,
        to_date=end,
        cardboard_item=cardboard_item,
        supplier=supplier,
        status=status_value,
        item_groups=[context.cardboard_item_group, *get_descendants_of("Item Group", context.cardboard_item_group)],
        item_codes=item_codes,
    )


def _scope_payload(filters):
    return {
        "company": filters.context.company,
        "warehouse": filters.context.warehouse,
        "cardboard_item_group": filters.context.cardboard_item_group,
        "cardboard_item": filters.cardboard_item,
    }


def _placeholders(values):
    return ", ".join(["%s"] * len(values))


def _item_filter(filters, field="item"):
    if filters.cardboard_item:
        return f" and {field} = %s", [filters.cardboard_item]
    return "", []


def _docstatus_filter(alias, status):
    if not status or status == "all":
        return "", []
    return f" and {alias}.docstatus = %s", [STATUS_VALUES[status]]


def _supply_totals(filters, status="submitted"):
    item_filter, item_values = _item_filter(filters, "supply.item")
    status_filter, status_values = _docstatus_filter("supply", status)
    groups = _placeholders(filters.item_groups)
    row = frappe.db.sql(
        f"""select count(supply.name) as count,
                coalesce(sum(supply.net_weight), 0) as quantity,
                coalesce(sum(supply.payable_weight), 0) as payable_weight,
                coalesce(sum(supply.total_amount), 0) as value
            from `tabCardboard Supply` supply
            inner join `tabWarehouse` warehouse on warehouse.name = supply.warehouse
            inner join `tabItem` item on item.name = supply.item
            where supply.posting_date between %s and %s
                and supply.warehouse = %s
                and warehouse.company = %s
                and item.item_group in ({groups})
                {status_filter}{item_filter}""",
        (filters.from_date, filters.to_date, filters.context.warehouse, filters.context.company,
         *filters.item_groups, *status_values, *item_values),
        as_dict=True,
    )[0]
    return {
        "count": int(row.count or 0),
        "quantity": flt(row.quantity),
        "payable_weight": flt(row.payable_weight),
        "value": flt(row.value),
    }


def _sale_totals(filters, status="submitted", buyer_text=None):
    item_filter, item_values = _item_filter(filters, "sale.item")
    status_filter, status_values = _docstatus_filter("sale", status)
    buyer_filter = ""
    buyer_values = []
    if buyer_text:
        buyer_filter = " and sale.buyer_name like %s"
        buyer_values.append(f"%{buyer_text}%")
    groups = _placeholders(filters.item_groups)
    row = frappe.db.sql(
        f"""select count(sale.name) as count,
                coalesce(sum(sale.quantity), 0) as quantity,
                coalesce(sum(sale.total_amount), 0) as value
            from `tabCardboard Sale` sale
            inner join `tabWarehouse` warehouse on warehouse.name = sale.warehouse
            inner join `tabItem` item on item.name = sale.item
            where sale.posting_date between %s and %s
                and sale.company = %s
                and sale.warehouse = %s
                and warehouse.company = %s
                and item.item_group in ({groups})
                {status_filter}{item_filter}{buyer_filter}""",
        (filters.from_date, filters.to_date, filters.context.company, filters.context.warehouse,
         filters.context.company, *filters.item_groups, *status_values, *item_values, *buyer_values),
        as_dict=True,
    )[0]
    return {"count": int(row.count or 0), "quantity": flt(row.quantity), "value": flt(row.value)}


def _payment_totals(filters):
    item_filter, item_values = _item_filter(filters, "supply.item")
    groups = _placeholders(filters.item_groups)
    supplier_filter = ""
    supplier_values = []
    if filters.supplier:
        supplier_filter = " and payment.supplier = %s"
        supplier_values.append(filters.supplier)
    row = frappe.db.sql(
        f"""select count(distinct payment.name) as count,
                coalesce(sum(native_payment.paid_amount), 0) as amount
            from `tabCardboard Supplier Payment` payment
            inner join `tabPayment Entry` native_payment
                on native_payment.name = payment.payment_entry
                and native_payment.docstatus = 1
                and native_payment.payment_type = 'Pay'
                and native_payment.party_type = 'Supplier'
            where payment.docstatus = 1
                and payment.posting_date between %s and %s
                and payment.company = %s
                {supplier_filter}
                and exists (
                    select 1
                    from `tabPayment Entry Reference` reference
                    inner join `tabPurchase Invoice` invoice
                        on invoice.name = reference.reference_name
                        and reference.reference_doctype = 'Purchase Invoice'
                        and invoice.docstatus = 1
                        and invoice.company = %s
                    inner join `tabCardboard Supply` supply
                        on supply.name = invoice.custom_cardboard_supply
                    inner join `tabWarehouse` warehouse on warehouse.name = supply.warehouse
                    inner join `tabItem` item on item.name = supply.item
                    where reference.parent = native_payment.name
                        and reference.parenttype = 'Payment Entry'
                        and supply.warehouse = %s
                        and warehouse.company = %s
                        and item.item_group in ({groups})
                        {item_filter}
                )""",
        (filters.from_date, filters.to_date, filters.context.company, *supplier_values,
         filters.context.company, filters.context.warehouse, filters.context.company,
         *filters.item_groups, *item_values),
        as_dict=True,
    )[0]
    return {"count": int(row.count or 0), "amount": flt(row.amount)}


def _expense_conditions(filters, alias="expense"):
    status = filters.status or "submitted"
    if status == "submitted":
        return f" and {alias}.docstatus = 1 and native_journal.docstatus = 1", []
    if status == "draft":
        return f" and {alias}.docstatus = 0", []
    if status == "cancelled":
        return f" and {alias}.docstatus = 2 and (native_journal.docstatus = 2 or native_journal.name is null)", []
    return "", []


def _expense_totals(filters):
    status_filter, status_values = _expense_conditions(filters)
    row = frappe.db.sql(
        f"""select count(expense.name) as count,
                coalesce(sum(expense.amount), 0) as amount
            from `tabQuick Expense` expense
            left join `tabJournal Entry` native_journal on native_journal.name = expense.accounting_document
            where expense.posting_date between %s and %s
                and expense.company = %s
                {status_filter}""",
        (filters.from_date, filters.to_date, filters.context.company, *status_values),
        as_dict=True,
    )[0]
    return {"count": int(row.count or 0), "amount": flt(row.amount)}


def _inventory_movement_data(filters):
    groups = _placeholders(filters.item_groups)
    item_filter_supply, item_values_supply = _item_filter(filters, "supply.item")
    item_filter_sale, item_values_sale = _item_filter(filters, "sale.item")
    supply_rows = frappe.db.sql(
        f"""select supply.posting_date, supply.item, item.item_name,
                coalesce(sum(supply.net_weight), 0) as quantity
            from `tabCardboard Supply` supply
            inner join `tabWarehouse` warehouse on warehouse.name = supply.warehouse
            inner join `tabItem` item on item.name = supply.item
            where supply.docstatus = 1
                and supply.posting_date between %s and %s
                and supply.warehouse = %s
                and warehouse.company = %s
                and item.item_group in ({groups})
                {item_filter_supply}
            group by supply.posting_date, supply.item, item.item_name
            order by supply.posting_date, supply.item""",
        (filters.from_date, filters.to_date, filters.context.warehouse, filters.context.company,
         *filters.item_groups, *item_values_supply),
        as_dict=True,
    )
    sale_rows = frappe.db.sql(
        f"""select sale.posting_date, sale.item, item.item_name,
                coalesce(sum(sale.quantity), 0) as quantity
            from `tabCardboard Sale` sale
            inner join `tabWarehouse` warehouse on warehouse.name = sale.warehouse
            inner join `tabItem` item on item.name = sale.item
            where sale.docstatus = 1
                and sale.posting_date between %s and %s
                and sale.company = %s
                and sale.warehouse = %s
                and warehouse.company = %s
                and item.item_group in ({groups})
                {item_filter_sale}
            group by sale.posting_date, sale.item, item.item_name
            order by sale.posting_date, sale.item""",
        (filters.from_date, filters.to_date, filters.context.company, filters.context.warehouse,
         filters.context.company, *filters.item_groups, *item_values_sale),
        as_dict=True,
    )
    by_date = defaultdict(lambda: {"inbound": 0.0, "outbound": 0.0, "net": 0.0})
    by_item = defaultdict(lambda: {"item_name": None, "inbound": 0.0, "outbound": 0.0, "net": 0.0})
    for row in supply_rows:
        date_key = str(row.posting_date)
        item_key = row.item
        quantity = flt(row.quantity)
        by_date[date_key]["inbound"] += quantity
        by_date[date_key]["net"] += quantity
        by_item[item_key]["item_name"] = row.item_name or item_key
        by_item[item_key]["inbound"] += quantity
        by_item[item_key]["net"] += quantity
    for row in sale_rows:
        date_key = str(row.posting_date)
        item_key = row.item
        quantity = flt(row.quantity)
        by_date[date_key]["outbound"] += quantity
        by_date[date_key]["net"] -= quantity
        by_item[item_key]["item_name"] = row.item_name or item_key
        by_item[item_key]["outbound"] += quantity
        by_item[item_key]["net"] -= quantity
    for values in (*by_date.values(), *by_item.values()):
        for key in ("inbound", "outbound", "net"):
            values[key] = flt(values[key])
    inbound = flt(sum(values["inbound"] for values in by_date.values()))
    outbound = flt(sum(values["outbound"] for values in by_date.values()))
    return {
        "inbound_quantity": inbound,
        "outbound_quantity": outbound,
        "net_quantity": flt(inbound - outbound),
        "by_date": [{"date": key, **by_date[key]} for key in sorted(by_date)],
        "by_item": [
            {"item": key, **by_item[key]} for key in sorted(by_item, key=lambda value: (by_item[value]["item_name"], value))
        ],
    }


def _scope_supply_history(filters):
    item_filter, item_values = _item_filter(filters, "supply.item")
    groups = _placeholders(filters.item_groups)
    return frappe.db.sql(
        f"""select supply.name, supply.posting_date, supply.item, item.item_name,
                supply.payable_weight, supply.total_amount
            from `tabCardboard Supply` supply
            inner join `tabWarehouse` warehouse on warehouse.name = supply.warehouse
            inner join `tabItem` item on item.name = supply.item
            where supply.docstatus = 1
                and supply.supplier = %s
                and supply.posting_date between %s and %s
                and supply.warehouse = %s
                and warehouse.company = %s
                and item.item_group in ({groups})
                {item_filter}
            order by supply.posting_date desc, supply.name desc""",
        (filters.supplier, filters.from_date, filters.to_date, filters.context.warehouse,
         filters.context.company, *filters.item_groups, *item_values),
        as_dict=True,
    )


def _scope_payment_history(filters):
    groups = _placeholders(filters.item_groups)
    return frappe.db.sql(
        f"""select payment.name, payment.posting_date, native_payment.paid_amount,
                payment.mode_of_payment
            from `tabCardboard Supplier Payment` payment
            inner join `tabPayment Entry` native_payment
                on native_payment.name = payment.payment_entry
                and native_payment.docstatus = 1
                and native_payment.payment_type = 'Pay'
                and native_payment.party_type = 'Supplier'
            where payment.docstatus = 1
                and payment.supplier = %s
                and payment.posting_date between %s and %s
                and payment.company = %s
                and exists (
                    select 1
                    from `tabPayment Entry Reference` reference
                    inner join `tabPurchase Invoice` invoice
                        on invoice.name = reference.reference_name
                        and reference.reference_doctype = 'Purchase Invoice'
                        and invoice.docstatus = 1
                        and invoice.company = %s
                    inner join `tabCardboard Supply` supply
                        on supply.name = invoice.custom_cardboard_supply
                    inner join `tabWarehouse` warehouse on warehouse.name = supply.warehouse
                    inner join `tabItem` item on item.name = supply.item
                    where reference.parent = native_payment.name
                        and reference.parenttype = 'Payment Entry'
                        and supply.warehouse = %s
                        and warehouse.company = %s
                        and item.item_group in ({groups})
                )
            order by payment.posting_date desc, payment.name desc""",
        (filters.supplier, filters.from_date, filters.to_date, filters.context.company,
         filters.context.company, filters.context.warehouse, filters.context.company,
         *filters.item_groups),
        as_dict=True,
    )


def _current_supplier_outstanding(filters):
    groups = _placeholders(filters.item_groups)
    row = frappe.db.sql(
        f"""select coalesce(sum(invoice.outstanding_amount), 0) as outstanding
            from `tabPurchase Invoice` invoice
            inner join `tabCardboard Supply` supply
                on supply.name = invoice.custom_cardboard_supply
            inner join `tabWarehouse` warehouse on warehouse.name = supply.warehouse
            inner join `tabItem` item on item.name = supply.item
            where invoice.docstatus = 1
                and invoice.supplier = %s
                and invoice.company = %s
                and supply.warehouse = %s
                and warehouse.company = %s
                and item.item_group in ({groups})""",
        (filters.supplier, filters.context.company, filters.context.warehouse,
         filters.context.company, *filters.item_groups),
        as_dict=True,
    )[0]
    return flt(row.outstanding)


def _supplier_identity(supplier):
    return frappe.db.get_value(
        "Supplier", supplier, ["name", "supplier_name", "supplier_group", "disabled"], as_dict=True
    )


@frappe.whitelist()
def get_operations_summary(from_date=None, to_date=None, cardboard_item=None):
    """Return scoped submitted operations and movement for a date range."""
    filters = _context(
        from_date,
        to_date,
        cardboard_item,
        required_doctypes=("Cardboard Supply", "Cardboard Sale", "Quick Expense", "Cardboard Supplier Payment"),
    )
    supplies = _supply_totals(filters)
    sales = _sale_totals(filters)
    payments = _payment_totals(filters)
    expenses = _expense_totals(filters)
    movement = _inventory_movement_data(filters)
    return {
        "from_date": str(filters.from_date),
        "to_date": str(filters.to_date),
        "scope": _scope_payload(filters),
        "supplies": supplies,
        "sales": sales,
        "expenses": expenses,
        "supplier_payments": payments,
        "inventory_movement": movement,
    }


@frappe.whitelist()
def get_sales_summary(from_date=None, to_date=None, cardboard_item=None, buyer_text=None, status=None):
    """Return informational Cardboard Sale totals; no revenue meaning is implied."""
    filters = _context(
        from_date,
        to_date,
        cardboard_item,
        status=status,
        required_doctypes=("Cardboard Sale",),
    )
    totals = _sale_totals(filters, filters.status, buyer_text)
    groups = _placeholders(filters.item_groups)
    item_filter, item_values = _item_filter(filters, "sale.item")
    status_filter, status_values = _docstatus_filter("sale", filters.status)
    buyer_filter = " and sale.buyer_name like %s" if buyer_text else ""
    buyer_values = [f"%{buyer_text}%"] if buyer_text else []
    by_item = frappe.db.sql(
        f"""select sale.item, item.item_name,
                count(sale.name) as count,
                coalesce(sum(sale.quantity), 0) as quantity,
                coalesce(sum(sale.total_amount), 0) as value
            from `tabCardboard Sale` sale
            inner join `tabWarehouse` warehouse on warehouse.name = sale.warehouse
            inner join `tabItem` item on item.name = sale.item
            where sale.posting_date between %s and %s
                and sale.company = %s
                and sale.warehouse = %s
                and warehouse.company = %s
                and item.item_group in ({groups})
                {status_filter}{item_filter}{buyer_filter}
            group by sale.item, item.item_name
            order by item.item_name, sale.item""",
        (filters.from_date, filters.to_date, filters.context.company, filters.context.warehouse,
         filters.context.company, *filters.item_groups, *status_values, *item_values, *buyer_values),
        as_dict=True,
    )
    return {
        "from_date": str(filters.from_date),
        "to_date": str(filters.to_date),
        "status": filters.status,
        "scope": _scope_payload(filters),
        "sale_count": totals["count"],
        "total_quantity": totals["quantity"],
        "total_informational_value": totals["value"],
        "by_item": [
            {"item": row.item, "item_name": row.item_name or row.item,
             "count": int(row.count or 0), "quantity": flt(row.quantity), "value": flt(row.value)}
            for row in by_item
        ],
    }


@frappe.whitelist()
def get_supplier_summary(supplier, from_date=None, to_date=None):
    """Return operational supplier history plus current ERPNext outstanding."""
    filters = _context(
        from_date,
        to_date,
        supplier=supplier,
        required_doctypes=("Cardboard Supply", "Cardboard Supplier Payment", "Supplier"),
    )
    identity = _supplier_identity(supplier)
    supply_rows = _scope_supply_history(filters)
    payment_rows = _scope_payment_history(filters)
    current_outstanding = _current_supplier_outstanding(filters)
    return {
        "supplier": {
            "name": identity.name,
            "supplier_name": identity.supplier_name or identity.name,
            "supplier_group": identity.supplier_group,
            "disabled": bool(identity.disabled),
        },
        "from_date": str(filters.from_date),
        "to_date": str(filters.to_date),
        "scope": _scope_payload(filters),
        "supply_count": len(supply_rows),
        "supplied_payable_weight": flt(sum(flt(row.payable_weight) for row in supply_rows)),
        "supply_value": flt(sum(flt(row.total_amount) for row in supply_rows)),
        "supplier_payments": flt(sum(flt(row.paid_amount) for row in payment_rows)),
        "outstanding": current_outstanding,
        "outstanding_semantics": "current_erpnext_purchase_invoice_outstanding",
        "supply_history": [
            {"supply": row.name, "posting_date": str(row.posting_date), "item": row.item,
             "item_name": row.item_name or row.item, "payable_weight": flt(row.payable_weight),
             "value": flt(row.total_amount)}
            for row in supply_rows
        ],
        "payment_history": [
            {"payment": row.name, "posting_date": str(row.posting_date),
             "amount": flt(row.paid_amount), "mode_of_payment": row.mode_of_payment}
            for row in payment_rows
        ],
    }


@frappe.whitelist()
def get_supplier_statement(supplier, from_date=None, to_date=None):
    """Stable alias for the normalized supplier summary contract."""
    return get_supplier_summary(supplier, from_date, to_date)


@frappe.whitelist()
def get_expense_summary(from_date=None, to_date=None, expense_account=None, status=None):
    """Return Quick Expense totals with native Journal Entry state enforced for submitted rows."""
    filters = _context(
        from_date,
        to_date,
        status=status,
        required_doctypes=("Quick Expense",),
    )
    status_filter, status_values = _expense_conditions(filters)
    account_filter = " and expense.expense_account = %s" if expense_account else ""
    account_values = [expense_account] if expense_account else []
    rows = frappe.db.sql(
        f"""select expense.expense_account, account.account_name,
                count(expense.name) as count,
                coalesce(sum(expense.amount), 0) as amount
            from `tabQuick Expense` expense
            left join `tabJournal Entry` native_journal on native_journal.name = expense.accounting_document
            left join `tabAccount` account on account.name = expense.expense_account
            where expense.posting_date between %s and %s
                and expense.company = %s
                {status_filter}{account_filter}
            group by expense.expense_account, account.account_name
            order by account.account_name, expense.expense_account""",
        (filters.from_date, filters.to_date, filters.context.company, *status_values, *account_values),
        as_dict=True,
    )
    return {
        "from_date": str(filters.from_date),
        "to_date": str(filters.to_date),
        "status": filters.status,
        "scope": _scope_payload(filters),
        "expense_count": int(sum(int(row.count or 0) for row in rows)),
        "total_expense_amount": flt(sum(flt(row.amount) for row in rows)),
        "by_account": [
            {"account": row.expense_account, "account_name": row.account_name or row.expense_account,
             "count": int(row.count or 0), "amount": flt(row.amount)}
            for row in rows
        ],
    }


@frappe.whitelist()
def get_inventory_movement(from_date=None, to_date=None, cardboard_item=None):
    """Return scoped inbound/outbound movement only, never a stock balance."""
    filters = _context(
        from_date,
        to_date,
        cardboard_item,
        required_doctypes=("Cardboard Supply", "Cardboard Sale"),
    )
    return {
        "from_date": str(filters.from_date),
        "to_date": str(filters.to_date),
        "scope": _scope_payload(filters),
        **_inventory_movement_data(filters),
    }
