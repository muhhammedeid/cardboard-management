frappe.provide("cardboard_management");

frappe.ui.form.on("Cardboard Supply", {
	refresh(frm) {
		toggle_discount_value(frm);
		add_scale_capture_actions(frm);
	},
	discount_type(frm) {
		if (frm.doc.discount_type === "No Discount") {
			frm.set_value("discount_value", 0);
		}
		toggle_discount_value(frm);
		calculate_totals(frm);
	},
	discount_value: calculate_totals,
	gross_weight: calculate_totals,
	tare_weight: calculate_totals,
	rate_per_kg: calculate_totals,
});

function toggle_discount_value(frm) {
	const has_discount = Boolean(frm.doc.discount_type) && frm.doc.discount_type !== "No Discount";
	frm.toggle_display("discount_value", has_discount);
}

function calculate_totals(frm) {
	const net_weight = flt(frm.doc.gross_weight) - flt(frm.doc.tare_weight);
	let discount_weight = 0;

	if (frm.doc.discount_type === "Kg") {
		discount_weight = flt(frm.doc.discount_value);
	} else if (frm.doc.discount_type === "Percentage") {
		discount_weight = net_weight * flt(frm.doc.discount_value) / 100;
	}

	const payable_weight = net_weight - discount_weight;
	frm.set_value("net_weight", net_weight);
	frm.set_value("discount_weight", discount_weight);
	frm.set_value("payable_weight", payable_weight);
	frm.set_value("total_amount", payable_weight * flt(frm.doc.rate_per_kg));
}

function add_scale_capture_actions(frm) {
	if (frm.doc.docstatus !== 0) {
		return;
	}

	frm.add_custom_button(
		__("Capture Gross Weight"),
		() => capture_scale_weight(frm, "gross_weight"),
		__("Electronic Scale"),
	);
	frm.add_custom_button(
		__("Capture Tare Weight"),
		() => capture_scale_weight(frm, "tare_weight"),
		__("Electronic Scale"),
	);
}

async function capture_scale_weight(frm, target_field) {
	const reader = cardboard_management.scale_reader;
	if (!reader?.read_weight) {
		frappe.msgprint(__("Electronic scale integration is not configured."));
		return;
	}

	try {
		const weight = await reader.read_weight({ frm, target_field });
		await frm.set_value(target_field, flt(weight));
	} catch {
		frappe.msgprint({
			title: __("Scale Capture Failed"),
			message: __("The scale gateway could not provide a weight."),
			indicator: "red",
		});
	}
}
