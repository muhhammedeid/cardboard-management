"""Database-free contract for the app-owned operational workspace."""
import json
import unittest
from pathlib import Path

WORKSPACE = (Path(__file__).resolve().parents[1] / "cardboard_management" /
             "workspace" / "cardboard_management" / "cardboard_management.json")


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
            ("Cardboard Supplies", "DocType", "Cardboard Supply", "List"),
            ("Suppliers", "DocType", "Supplier", "List"),
            ("Payment Entries", "DocType", "Payment Entry", "List"),
            ("Stock Balance", "Report", "Stock Balance", None),
            ("Items", "DocType", "Item", "List"),
            ("Warehouses", "DocType", "Warehouse", "List"),
        ]
        self.assertEqual([(s["label"], s["type"], s["link_to"], s.get("doc_view"))
                          for s in workspace["shortcuts"]], expected)
        blocks = json.loads(workspace["content"])
        self.assertEqual([b["data"]["shortcut_name"] for b in blocks if b["type"] == "shortcut"],
                         [s[0] for s in expected])
        cards = [link["label"] for link in workspace["links"] if link["type"] == "Card Break"]
        self.assertEqual(cards, ["Purchasing / Supplies", "Suppliers & Payments", "Inventory", "Reports"])
        self.assertEqual([b["data"]["card_name"] for b in blocks if b["type"] == "card"], cards)
        reports = {link["label"]: link["link_to"] for link in workspace["links"]
                   if link.get("link_type") == "Report"}
        self.assertEqual(reports, {"Stock Balance": "Stock Balance",
                                  "Supplier Outstanding": "Accounts Payable",
                                  "Purchase Register": "Purchase Register"})
        for link in workspace["links"]:
            if link.get("link_type") == "Report":
                self.assertEqual(link["is_query_report"], 1)
        text = " ".join(b["data"].get("text", "") for b in blocks)
        for label in ("Quick Actions", "Operations", "Expenses", "Dashboard", "Scale Integration", "Not implemented yet"):
            self.assertIn(label, text)
        for field in ("charts", "number_cards", "custom_blocks", "quick_lists"):
            self.assertEqual(workspace[field], [])
        self.assertNotIn("href=", text)


if __name__ == "__main__":
    unittest.main()
