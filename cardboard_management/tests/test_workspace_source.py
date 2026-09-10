"""Database-free contract for the app-owned operational workspace."""
import json
import runpy
import unittest
from pathlib import Path

WORKSPACE = (Path(__file__).resolve().parents[1] / "cardboard_management" /
             "workspace" / "cardboard_management" / "cardboard_management.json")

NUMBER_CARDS = [
    "Today's Supplies Weight", "Today's Purchase Amount", "Today's Supplier Payments",
    "Today's Expenses", "Current Stock Weight", "Supplier Outstanding",
    "This Month Purchased Weight", "This Month Purchase Cost", "This Month Expenses",
    "This Month Paid to Suppliers",
]
CHARTS = [
    "Daily Supplied Weight", "Purchases by Cardboard Type", "Top Suppliers",
    "Supplier Outstanding",
]
QUICK_ACTIONS = [
    ("New Cardboard Supply", "DocType", "Cardboard Supply", "New"),
    ("New Supplier Payment", "DocType", "Cardboard Supplier Payment", "New"),
    ("New Expense", "DocType", "Quick Expense", "New"),
    ("New Supplier", "DocType", "Supplier", "New"),
]
MAIN_AREAS = [
    ("Supplies", "DocType", "Cardboard Supply", "List"),
    ("Suppliers", "DocType", "Supplier", "List"),
    ("Payments", "DocType", "Cardboard Supplier Payment", "List"),
    ("Expenses", "DocType", "Quick Expense", "List"),
    ("Inventory", "Page", "inventory-operational-view", None),
    ("Reports", "Report", "Accounts Payable", None),
]


class TestWorkspaceSource(unittest.TestCase):
    def test_public_operational_workspace_prioritizes_routes_for_daily_work(self):
        self.assertTrue(WORKSPACE.is_file(), "Ship the workspace in the custom app")
        workspace = json.loads(WORKSPACE.read_text(encoding="utf-8"))
        for field in ("name", "title", "label", "module"):
            self.assertEqual(workspace[field], "Cardboard Management")
        self.assertEqual(workspace["doctype"], "Workspace")
        self.assertEqual(workspace["public"], 1)
        self.assertEqual(workspace["is_hidden"], 0)
        self.assertEqual(workspace["hide_custom"], 1)
        self.assertEqual(workspace["for_user"], "")

        shortcuts = [(s["label"], s["type"], s["link_to"], s.get("doc_view"))
                     for s in workspace["shortcuts"]]
        self.assertEqual(shortcuts, QUICK_ACTIONS + MAIN_AREAS + [
            ("Settings", "DocType", "Cardboard Dashboard Settings", None),
        ])
        self.assertNotIn("Payment Entry", [shortcut[2] for shortcut in shortcuts])

        blocks = json.loads(workspace["content"])
        shortcut_names = [b["data"]["shortcut_name"] for b in blocks if b["type"] == "shortcut"]
        self.assertEqual(shortcut_names, [item[0] for item in QUICK_ACTIONS + MAIN_AREAS])
        self.assertLess(
            next(i for i, b in enumerate(blocks) if b["id"] == "cm-quick-actions"),
            next(i for i, b in enumerate(blocks) if b["id"] == "cm-main-areas"),
        )
        self.assertLess(
            next(i for i, b in enumerate(blocks) if b["id"] == "cm-main-areas"),
            next(i for i, b in enumerate(blocks) if b["id"] == "cm-today"),
        )

        cards = [link["label"] for link in workspace["links"] if link["type"] == "Card Break"]
        self.assertEqual(cards, ["Purchasing / Supplies", "Suppliers & Payments", "Expenses",
                                 "Inventory", "Reports", "Settings"])
        self.assertEqual([b["data"]["card_name"] for b in blocks if b["type"] == "card"], cards)
        reports = {link["label"]: link["link_to"] for link in workspace["links"]
                   if link.get("link_type") == "Report"}
        self.assertEqual(reports, {"Stock Balance": "Stock Balance",
                                   "Supplier Outstanding": "Accounts Payable",
                                   "Purchase Register": "Purchase Register"})
        for link in workspace["links"]:
            if link.get("link_type") == "Report":
                self.assertEqual(link["is_query_report"], 1)

        self.assertEqual([row["number_card_name"] for row in workspace["number_cards"]], NUMBER_CARDS)
        self.assertEqual([b["data"]["number_card_name"] for b in blocks
                          if b["type"] == "number_card"], NUMBER_CARDS)
        self.assertEqual([row["chart_name"] for row in workspace["charts"]], CHARTS)
        self.assertEqual([b["data"]["chart_name"] for b in blocks if b["type"] == "chart"], CHARTS)

        text = " ".join(b["data"].get("text", "") for b in blocks)
        for label in ("Operational Home", "Quick Actions", "Main Work Areas", "TODAY", "CURRENT",
                      "THIS MONTH", "Charts", "Scale Integration", "Not implemented yet"):
            self.assertIn(label, text)
        for field in ("custom_blocks", "quick_lists"):
            self.assertEqual(workspace[field], [])
        self.assertNotIn("href=", text)

    def test_content_builder_reproduces_committed_workspace(self):
        builder = runpy.run_path(str(WORKSPACE.parent.parent / "content_builder.py"))
        workspace = json.loads(WORKSPACE.read_text(encoding="utf-8"))
        self.assertEqual(builder["build_workspace"](), workspace)


if __name__ == "__main__":
    unittest.main()
