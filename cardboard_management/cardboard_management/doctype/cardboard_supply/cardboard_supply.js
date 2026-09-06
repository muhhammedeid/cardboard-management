frappe.ui.form.on("Cardboard Supply", {
	gross_weight: calculate_totals,
	tare_weight: calculate_totals,
	rate_per_kg: calculate_totals,
});

function calculate_totals(frm) {
	const net_weight = flt(frm.doc.gross_weight) - flt(frm.doc.tare_weight);
	frm.set_value("net_weight", net_weight);
	frm.set_value("total_amount", net_weight * flt(frm.doc.rate_per_kg));
}
