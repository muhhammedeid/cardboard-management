from frappe.sessions import get_csrf_token

import frappe

from cardboard_management.cardboard_management.api.ai_chat import can_use_ai_assistant


@frappe.whitelist(methods=["GET"])
def get_session_context():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)

    return {
        "user": frappe.session.user,
        "csrf_token": get_csrf_token(),
        "can_use_ai_assistant": can_use_ai_assistant(),
    }
