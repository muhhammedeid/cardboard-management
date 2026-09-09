frappe.ui.form.on("Cardboard Supplier Payment", {
	refresh(frm) {
		add_payment_summary_headline(frm);
		// The primary action stays the native save+submit lifecycle; the label is
		// the supported operational one and no custom accounting runs client-side.
		if (frm.doc.docstatus === 0) {
			frm.page.set_primary_action( __("Save and Submit Payment"), () => {
				frm.savesubmit();
			});
		}
	},
});

function add_payment_summary_headline(frm) {
	if (!frm.doc.current_supplier_outstanding && frm.doc.current_supplier_outstanding !== 0) {
		return;
	}
	frm.dashboard.set_headline(
		__("Current Supplier Outstanding: {0}", [
			frappe.utils.fmt_money(frm.doc.current_supplier_outstanding),
		]),
		"blue"
	);
}
