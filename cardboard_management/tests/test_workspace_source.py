"""Database-free contract for the app-owned operational workspace."""
import json
import runpy
import unittest
from pathlib import Path

WORKSPACE = (Path(__file__).resolve().parents[1] / "cardboard_management" /
             "workspace" / "cardboard_management" / "cardboard_management.json")

NUMBER_CARDS = [
    "Today's Supplies Weight",
    "Today's Purchase Amount",
    "Today's Supplier Payments",
    "Today's Expenses",
    "Current Stock Weight",
    "Supplier Outstanding",
    "This Month Purchased Weight",
    "This Month Purchase Cost",
    "This Month Expenses",
    "This Month Paid to Suppliers",
]
CHARTS = [
    "Daily Supplied Weight",
    "Purchases by Cardboard Type",
    "Top Suppliers",
    "Supplier Outstanding",
]


class TestWorkspaceSource(unittest.TestCase):
    def test_public_operational_workspace_is_shipped_with_native_targets(self):
        self.assertTrue(WORKSPACE.is_file(), "Ship the workspace in the custom app")
        workspace = json.loads(WORKSPACE.read_text())
        for field in ("name", "title", "label", "module"):
            self.assertEqual(workspace[field], "Cardboard Management")
        self.assertEqual(workspace["doctype"], "Workspace")
        self.assertEqual(workspace["public"], 1)
        self.assertEqual(workspace["is_hidden"], 0)
        self.assertEqual(workspace["hide_custom"], 1)
        self.assertEqual(workspace["for_user"], "")
        expected = [
            ("New Cardboard Supply", "DocType", "Cardboard Supply", "New"),
            ("New Expense", "DocType", "Quick Expense", "New"),
            ("New Supplier", "DocType", "Supplier", "New"),
            ("New Supplier Payment", "DocType", "Payment Entry", "New"),
            ("Supplies", "DocType", "Cardboard Supply", "List"),
            ("Suppliers", "DocType", "Supplier", "List"),
            ("Payments", "DocType", "Payment Entry", "List"),
            ("Expenses", "DocType", "Quick Expense", "List"),
            ("Inventory", "Report", "Stock Balance", None),
            ("Reports", "Report", "Accounts Payable", None),
            ("Settings", "DocType", "Cardboard Dashboard Settings", None),
        ]
        self.assertEqual([(s["label"], s["type"], s["link_to"], s.get("doc_view"))
                          for s in workspace["shortcuts"]], expected)
        blocks = json.loads(workspace["content"])
        self.assertEqual([b["data"]["shortcut_name"] for b in blocks if b["type"] == "shortcut"],
                         ["Supplies", "Suppliers", "Payments", "Expenses", "Inventory",
                          "Reports", "Settings", "New Cardboard Supply", "New Expense",
                          "New Supplier", "New Supplier Payment"])
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
        for label in ("Operational Home", "Quick Actions", "TODAY", "CURRENT", "THIS MONTH",
                      "Charts", "Scale Integration", "Not implemented yet"):
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
