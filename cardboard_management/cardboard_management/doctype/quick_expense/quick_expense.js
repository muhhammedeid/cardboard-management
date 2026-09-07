frappe.ui.form.on("Quick Expense", {
	refresh(frm) {
		add_integration_indicators(frm);
		if (frm.doc.docstatus === 1 && !frm.doc.accounting_document) {
			// Submitted without accounting (e.g. during a retry); try to complete linkage.
			frm.add_custom_button(__("Create Accounting Entry"), () => create_accounting_entry(frm));
		}
	},
});

function add_integration_indicators(frm) {
	if (!frm.doc.accounting_status) return;
	const colors = {
		"Not Integrated": "orange",
		"Integrated": "green",
		"Cancelled": "red",
	};
	frm.dashboard.set_headline(
		__("Accounting: {0}", [__(frm.doc.accounting_status)]),
		colors[frm.doc.accounting_status] || "blue"
	);
}

function create_accounting_entry(frm) {
	frm.call({
		doc: frm.doc,
		method: "make_journal_entry",
		freeze: true,
		freeze_message: __("Creating accounting entry..."),
		callback: () => frm.reload_doc(),
	});
}
