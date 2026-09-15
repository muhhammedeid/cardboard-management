from frappe.sessions import get_csrf_token

import frappe


@frappe.whitelist(methods=["GET"])
def get_session_context():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)

    return {
        "user": frappe.session.user,
        "csrf_token": get_csrf_token(),
    }
