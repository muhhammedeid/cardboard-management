import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate
from frappe.utils.nestedset import get_descendants_of

from cardboard_management.cardboard_management.api import supply as api


class TestSupplyContract(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings = frappe.get_cached_doc("Cardboard Dashboard Settings")
        groups = [settings.cardboard_item_group]
        groups.extend(get_descendants_of("Item Group", settings.cardboard_item_group))
        cls.warehouse = settings.default_warehouse
        cls.item = frappe.db.get_value(
            "Item", {"item_group": ["in", groups], "disabled": 0, "is_stock_item": 1, "stock_uom": "Kg"}, "name"
        )
        cls.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
        if not cls.item or not cls.supplier or not cls.warehouse:
            raise AssertionError("Supply contract tests require configured Supply masters")

    def make_values(self):
        return {
            "posting_date": nowdate(),
            "supplier": self.supplier,
            "item": self.item,
            "gross_weight": 1250,
            "tare_weight": 250,
            "rate_per_kg": 2.75,
            "discount_type": "No Discount",
            "discount_value": 0,
            "notes": "contract test",
        }

    def test_create_update_detail_list_and_capabilities(self):
        created = api.create_supply(**self.make_values())
        self.assertEqual(created["warehouse"], self.warehouse)
        self.assertEqual(created["net_weight"], 1000)
        self.assertEqual(created["payable_weight"], 1000)
        self.assertTrue(created["capabilities"]["can_submit"])

        updated = api.update_supply(created["name"], rate_per_kg=3, notes="updated")
        self.assertEqual(updated["rate_per_kg"], 3)
        self.assertEqual(updated["total_amount"], 3000)
        detail = api.get_supply(created["name"])
        self.assertEqual(detail["name"], created["name"])
        self.assertEqual(api.get_capabilities(created["name"])["capabilities"], detail["capabilities"])
        listed = api.list_supplies(status="Draft", page=1, page_size=1)
        self.assertEqual(len(listed["data"]), 1)
        self.assertIn("total", listed)

    def test_lookups_are_bounded_and_item_lookup_is_scoped(self):
        suppliers = api.lookup_suppliers(page_size=1000)
        items = api.lookup_items(page_size=1000)
        self.assertLessEqual(len(suppliers["data"]), api.MAX_PAGE_SIZE)
        self.assertLessEqual(len(items["data"]), api.MAX_PAGE_SIZE)
        self.assertTrue(all(row["stock_uom"] == "Kg" for row in items["data"]))

    def test_preview_returns_authoritative_derived_weights_without_persisting(self):
        baseline = frappe.db.count("Cardboard Supply")
        preview = api.preview_supply(
            **{
                **self.make_values(),
                "gross_weight": 4800,
                "tare_weight": 1650,
                "discount_type": "Kg",
                "discount_value": 50,
                "rate_per_kg": 0,
                "cmd": "cardboard_management.cardboard_management.api.supply.preview_supply",
            }
        )
        self.assertEqual(preview["net_weight"], 3150)
        self.assertEqual(preview["discount_weight"], 50)
        self.assertEqual(preview["payable_weight"], 3100)
        self.assertEqual(preview["total_amount"], 0)
        self.assertEqual(frappe.db.count("Cardboard Supply"), baseline)

    def test_submit_cancel_and_invalid_state(self):
        created = api.create_supply(**self.make_values())
        submitted = api.submit_supply(created["name"])
        self.assertEqual(submitted["docstatus"], 1)
        with self.assertRaises(frappe.ValidationError):
            api.update_supply(created["name"], notes="no")
        cancelled = api.cancel_supply(created["name"])
        self.assertEqual(cancelled["docstatus"], 2)
        with self.assertRaises(frappe.ValidationError):
            api.cancel_supply(created["name"])

    def test_scale_capture_is_draft_only_and_returns_authoritative_record(self):
        created = api.create_supply(**self.make_values())
        captured = api.capture_gross_weight(created["name"], 1400)
        self.assertEqual(captured["field"], "gross_weight")
        self.assertEqual(captured["weight"], 1400)
        self.assertEqual(captured["supply"]["gross_weight"], 1400)
        with self.assertRaises(frappe.ValidationError):
            api.capture_tare_weight(created["name"], None)
        api.submit_supply(created["name"])
        with self.assertRaises(frappe.ValidationError):
            api.capture_tare_weight(created["name"], 250)

    def test_print_contract_reuses_ticket_format(self):
        created = api.create_supply(**self.make_values())
        action = api.get_print_action(created["name"])
        self.assertEqual(action["format"], "Cardboard Supply Ticket")
        self.assertIn("printview", action["url"])

    def test_permission_denial_is_enforced(self):
        created = api.create_supply(**self.make_values())
        original_user = frappe.session.user
        try:
            frappe.set_user("Guest")
            with self.assertRaises(frappe.PermissionError):
                api.get_supply(created["name"])
        finally:
            frappe.set_user(original_user)
