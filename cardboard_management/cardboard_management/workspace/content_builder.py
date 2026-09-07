"""Deterministic workspace JSON renderer (encoding only; behavior is unopinionated)."""
import json
from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[2]
WORKSPACE = APP_PATH / "cardboard_management" / "workspace" / "cardboard_management" / "cardboard_management.json"

HERO = "Quick Actions"
COMING_SOON = "Coming Soon"
PLACEHOLDER_TEXT = "<span class=\"text-muted\">Expenses, Dashboard, and Scale Integration &mdash; Not implemented yet.</span>"
SEQUENCE_ID = 99.0

SHORTCUTS = [
    {"label": "New Cardboard Supply", "type": "DocType", "link_to": "Cardboard Supply", "doc_view": "New", "color": "Blue"},
    {"label": "New Expense", "type": "DocType", "link_to": "Quick Expense", "doc_view": "New", "color": "Red"},
    {"label": "Cardboard Supplies", "type": "DocType", "link_to": "Cardboard Supply", "doc_view": "List", "color": "Blue"},
    {"label": "Expenses", "type": "DocType", "link_to": "Quick Expense", "doc_view": "List", "color": "Red"},
    {"label": "Suppliers", "type": "DocType", "link_to": "Supplier", "doc_view": "List", "color": "Green"},
    {"label": "Payment Entries", "type": "DocType", "link_to": "Payment Entry", "doc_view": "List", "color": "Orange"},
    {"label": "Stock Balance", "type": "Report", "link_to": "Stock Balance", "color": "Grey"},
    {"label": "Items", "type": "DocType", "link_to": "Item", "doc_view": "List", "color": "Green"},
    {"label": "Warehouses", "type": "DocType", "link_to": "Warehouse", "doc_view": "List", "color": "Green"},
]

CARDS = [
    {
        "name": "Purchasing / Supplies",
        "link_to": "Purchase Invoice",
        "link_type": "DocType",
        "links": [
            {"label": "Cardboard Supply", "type": "Link", "link_type": "DocType", "link_to": "Cardboard Supply"},
            {"label": "Purchase Invoice", "type": "Link", "link_type": "DocType", "link_to": "Purchase Invoice"},
        ],
    },
    {
        "name": "Suppliers & Payments",
        "link_to": "Supplier",
        "link_type": "DocType",
        "links": [
            {"label": "Supplier", "type": "Link", "link_type": "DocType", "link_to": "Supplier"},
            {"label": "Payment Entry", "type": "Link", "link_type": "DocType", "link_to": "Payment Entry"},
        ],
    },
    {
        "name": "Expenses",
        "link_to": "Quick Expense",
        "link_type": "DocType",
        "links": [
            {"label": "Quick Expense", "type": "Link", "link_type": "DocType", "link_to": "Quick Expense"},
        ],
    },
    {
        "name": "Inventory",
        "link_to": "Item",
        "link_type": "DocType",
        "links": [
            {"label": "Stock Balance", "type": "Link", "link_type": "Report", "link_to": "Stock Balance"},
            {"label": "Item", "type": "Link", "link_type": "DocType", "link_to": "Item"},
            {"label": "Warehouse", "type": "Link", "link_type": "DocType", "link_to": "Warehouse"},
        ],
    },
    {
        "name": "Reports",
        "link_to": "Stock Balance",
        "link_type": "DocType",
        "links": [
            {"label": "Stock Balance", "type": "Link", "link_type": "Report", "link_to": "Stock Balance"},
            {"label": "Supplier Outstanding", "type": "Link", "link_type": "Report", "link_to": "Accounts Payable"},
            {"label": "Purchase Register", "type": "Link", "link_type": "Report", "link_to": "Purchase Register"},
        ],
    },
]

HEADER_HTML = '<span class="h4"><b>{title}</b></span>'


def build_links():
    links = []
    for card in CARDS:
        links.append({
            "dependencies": "", "hidden": 0, "is_query_report": 0,
            "label": card["name"], "link_count": len(card["links"]),
            "link_to": card["link_to"], "link_type": card["link_type"],
            "onboard": 0, "type": "Card Break",
        })
        for link in card["links"]:
            links.append({
                "dependencies": "", "hidden": 0,
                "is_query_report": 1 if link["link_type"] == "Report" else 0,
                "label": link["label"], "link_count": 0, "link_to": link["link_to"],
                "link_type": link["link_type"], "onboard": 0, "type": "Link",
            })
    return links


def build_content():
    blocks = [
        {"id": "cm-hero-header", "type": "header", "data": {"text": HEADER_HTML.format(title=HERO), "col": 12}},
    ]
    for index, shortcut in enumerate(SHORTCUTS[:3]):
        blocks.append({
            "id": f"cm-shortcut-{index}",
            "type": "shortcut",
            "data": {"shortcut_name": shortcut["label"], "col": 3},
        })
    blocks.append({"id": "cm-spacer-after-shortcuts", "type": "spacer", "data": {"col": 12}})
    blocks.append({
        "id": "cm-operations-header",
        "type": "header",
        "data": {"text": HEADER_HTML.format(title="Operations"), "col": 12},
    })
    for index, shortcut in enumerate(SHORTCUTS[3:6], start=3):
        blocks.append({
            "id": f"cm-shortcut-{index}",
            "type": "shortcut",
            "data": {"shortcut_name": shortcut["label"], "col": 3},
        })
    blocks.append({
        "id": "cm-spacer-after-operations-shortcuts",
        "type": "spacer",
        "data": {"col": 12},
    })
    for index, card in enumerate(CARDS):
        blocks.append({
            "id": f"cm-card-{index}",
            "type": "card",
            "data": {"card_name": card["name"], "col": 4},
        })
    blocks.append({"id": "cm-spacer-after-cards", "type": "spacer", "data": {"col": 12}})
    blocks.append({
        "id": "cm-inventory-header",
        "type": "header",
        "data": {"text": HEADER_HTML.format(title="Inventory"), "col": 12},
    })
    for index, shortcut in enumerate(SHORTCUTS[6:], start=6):
        blocks.append({
            "id": f"cm-shortcut-{index}",
            "type": "shortcut",
            "data": {"shortcut_name": shortcut["label"], "col": 3},
        })
    blocks.append({
        "id": "cm-placeholder-header",
        "type": "header",
        "data": {"text": HEADER_HTML.format(title=COMING_SOON), "col": 12},
    })
    blocks.append({
        "id": "cm-placeholder-text",
        "type": "paragraph",
        "data": {"text": PLACEHOLDER_TEXT, "col": 12},
    })
    return blocks


def build_workspace():
    return {
        "charts": [],
        "content": json.dumps(build_content()),
        "creation": "2026-09-07 10:30:00.000000",
        "custom_blocks": [],
        "docstatus": 0,
        "doctype": "Workspace",
        "for_user": "",
        "hide_custom": 1,
        "icon": "",
        "idx": 0,
        "is_hidden": 0,
        "label": "Cardboard Management",
        "links": build_links(),
        "modified": "2026-09-07 15:00:00.000000",
        "modified_by": "Administrator",
        "module": "Cardboard Management",
        "name": "Cardboard Management",
        "number_cards": [],
        "owner": "Administrator",
        "parent_page": "",
        "public": 1,
        "quick_lists": [],
        "restrict_to_domain": "",
        "roles": [],
        "sequence_id": SEQUENCE_ID,
        "shortcuts": [
            {
                "color": s["color"], "label": s["label"],
                "link_to": s["link_to"], "type": s["type"],
                **({"doc_view": s["doc_view"]} if s.get("doc_view") else {}),
            }
            for s in SHORTCUTS
        ],
        "title": "Cardboard Management",
    }


def main():
    WORKSPACE.parent.mkdir(parents=True, exist_ok=True)
    workspace = build_workspace()
    WORKSPACE.write_text(json.dumps(workspace, indent=1) + "\n")
    print(f"wrote {WORKSPACE}")


if __name__ == "__main__":
    main()
