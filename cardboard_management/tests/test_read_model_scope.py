"""Runtime contracts for P03-C03 inventory/dashboard read-model scope."""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate
from frappe.utils.nestedset import get_descendants_of

from cardboard_management import dashboard, inventory


class TestInventoryDashboardReadModelScope(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.context = inventory.get_inventory_context()
        cls.item = cls.context["items"][0].name if cls.context["items"] else None
        cls.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
        cls.alternate_warehouse = frappe.db.get_value(
            "Warehouse",
            {
                "company": cls.context.company,
                "name": ["!=", cls.context.warehouse],
                "disabled": 0,
                "is_group": 0,
            },
            "name",
        )
        if not cls.item or not cls.supplier or not cls.alternate_warehouse:
            raise unittest.SkipTest("P03-C03 site fixtures lack scoped item/supplier/warehouse")

    @staticmethod
    def _chart_values(chart):
        return dict(zip(chart["labels"], chart["datasets"][0]["values"]))

    @staticmethod
    def _raw_doc(doctype, name, values):
        document = frappe.get_doc({"doctype": doctype, "name": name, **values})
        document.flags.ignore_validate = True
        document.flags.ignore_permissions = True
        document.db_insert()
        frappe.db.set_value(doctype, name, "docstatus", 1, update_modified=False)
        return name

    def _insert_supply(self, suffix, warehouse, item, quantity):
        name = f"_P03C03 Supply {suffix} {frappe.generate_hash(length=6)}"
        return self._raw_doc(
            "Cardboard Supply",
            name,
            {
                "posting_date": nowdate(),
                "supplier": self.supplier,
                "item": item,
                "warehouse": warehouse,
                "gross_weight": quantity,
                "tare_weight": 0,
                "net_weight": quantity,
                "discount_type": "No Discount",
                "discount_value": 0,
                "discount_weight": 0,
                "payable_weight": quantity,
                "rate_per_kg": 1,
                "total_amount": quantity,
            },
        )

    def _insert_sale(self, suffix, warehouse, item, quantity):
        name = f"_P03C03 Sale {suffix} {frappe.generate_hash(length=6)}"
        return self._raw_doc(
            "Cardboard Sale",
            name,
            {
                "posting_date": nowdate(),
                "item": item,
                "quantity": quantity,
                "rate_per_kg": 1,
                "total_amount": quantity,
                "company": self.context.company,
                "warehouse": warehouse,
            },
        )

    def _make_non_cardboard_item(self):
        groups = [
            self.context.cardboard_item_group,
            *get_descendants_of("Item Group", self.context.cardboard_item_group),
        ]
        item_group = frappe.db.get_value(
            "Item Group",
            {"name": ["not in", groups], "is_group": 0},
            "name",
        )
        if not item_group:
            self.skipTest("Site has no non-cardboard leaf Item Group")
        item_code = f"_P03C03 Non Cardboard {frappe.generate_hash(length=8)}"
        item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_code,
                "item_group": item_group,
                "stock_uom": "Kg",
                "is_stock_item": 1,
                "is_purchase_item": 1,
            }
        ).insert(ignore_permissions=True)
        return item.name

    def test_current_inventory_is_scoped_to_settings_and_stock_balance(self):
        result = inventory.get_inventory_overview()
        self.assertTrue(result["is_today"])
        self.assertEqual(result["company"], self.context.company)
        self.assertEqual(result["warehouse"], self.context.warehouse)
        self.assertTrue({row["item_code"] for row in result["rows"]} <= {item.name for item in self.context["items"]})

        expected = sum(row["quantity"] for row in result["rows"])
        self.assertEqual(flt(result["summary"]["quantity"] or 0), flt(expected))
        self.assertEqual(
            flt(dashboard.get_metric_value("current_stock_weight")),
            flt(expected),
        )

    def test_historical_inventory_is_end_of_day_and_uses_same_scope(self):
        selected_date = frappe.utils.add_days(nowdate(), -1)
        result = inventory.get_inventory_overview(selected_date=selected_date)
        self.assertFalse(result["is_today"])
        self.assertEqual(result["selected_date"], str(selected_date))
        self.assertEqual(result["warehouse"], self.context.warehouse)
        self.assertTrue({row["item_code"] for row in result["rows"]} <= {item.name for item in self.context["items"]})

    def test_inventory_supports_all_and_single_cardboard_item_requests(self):
        all_result = inventory.get_inventory_overview()
        one_result = inventory.get_inventory_overview(item_code=self.item)
        self.assertEqual({row["item_code"] for row in one_result["rows"]}, {self.item} & {row["item_code"] for row in all_result["rows"]})
        self.assertEqual(one_result["warehouse"], all_result["warehouse"])
        self.assertEqual(one_result["company"], all_result["company"])

    def test_daily_activity_and_dashboard_supply_metrics_exclude_out_of_scope_rows(self):
        before_inventory = inventory.get_inventory_overview()["activity"]
        before_metric = dashboard.get_metric_value("today_supply_weight")
        before_daily = self._chart_values(dashboard.get_chart_data("daily_supplied_weight"))
        before_type = self._chart_values(dashboard.get_chart_data("purchases_by_type"))
        before_supplier = self._chart_values(dashboard.get_chart_data("top_suppliers"))

        non_cardboard_item = self._make_non_cardboard_item()
        self._insert_supply("default", self.context.warehouse, self.item, 7)
        self._insert_supply("other-warehouse", self.alternate_warehouse, self.item, 11)
        self._insert_supply("other-group", self.context.warehouse, non_cardboard_item, 13)
        self._insert_sale("default", self.context.warehouse, self.item, 3)
        self._insert_sale("other-warehouse", self.alternate_warehouse, self.item, 17)
        self._insert_sale("other-group", self.context.warehouse, non_cardboard_item, 19)

        after_inventory = inventory.get_inventory_overview()["activity"]
        self.assertEqual(flt(after_inventory["supplies"]["quantity"]) - flt(before_inventory["supplies"]["quantity"]), 7)
        self.assertEqual(flt(after_inventory["sales"]["quantity"]) - flt(before_inventory["sales"]["quantity"]), 3)
        self.assertEqual(
            flt(dashboard.get_metric_value("today_supply_weight")) - flt(before_metric),
            7,
        )

        today = str(nowdate())
        after_daily = self._chart_values(dashboard.get_chart_data("daily_supplied_weight"))
        self.assertEqual(flt(after_daily.get(today, 0)) - flt(before_daily.get(today, 0)), 7)

        after_type = self._chart_values(dashboard.get_chart_data("purchases_by_type"))
        self.assertEqual(flt(after_type.get(self.item, 0)) - flt(before_type.get(self.item, 0)), 7)

        after_supplier = self._chart_values(dashboard.get_chart_data("top_suppliers"))
        self.assertEqual(
            flt(after_supplier.get(self.supplier, 0)) - flt(before_supplier.get(self.supplier, 0)),
            7,
        )
