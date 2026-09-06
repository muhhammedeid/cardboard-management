frappe.provide("cardboard_management");

frappe.ui.form.on("Cardboard Supply", {
	refresh(frm) {
		toggle_discount_value(frm);
		add_scale_capture_actions(frm);
		add_record_payment_action(frm);
		add_integration_indicators(frm);
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

function add_record_payment_action(frm) {
	if (
		frm.doc.docstatus !== 1
		|| !frm.doc.purchase_invoice
		|| !(frm.doc.purchase_invoice_outstanding > 0)
	) {
		return;
	}

	frm.add_custom_button(__("Record Payment"), () => select_payment_account(frm));
}

function add_integration_indicators(frm) {
	const status = frm.doc.integration_status || (frm.doc.purchase_invoice ? "Integrated" : "Not Integrated");
	let label = __("Not Integrated");
	let color = "gray";
	let tooltip = __("No linked Purchase Invoice exists for this supply.");

	if (status === "Integrated") {
		label = __("Integrated");
		color = "green";
		tooltip = __("Linked Purchase Invoice is valid and submitted.");
		if (frm.doc.payment_status === "Paid") {
			label = __("Integrated - Paid");
		} else if (frm.doc.payment_status === "Partially Paid") {
			label = __("Integrated - Partially Paid");
		}
	} else if (status === "Invalid Link") {
		label = __("Invalid Link");
		color = "red";
		tooltip = __("Linked Purchase Invoice is cancelled or does not belong to this supply.");
	}

	frm.dashboard.set_headline(__("ERPNext Integration: {0}", [frappe.utils.escape_html(label)]), color);
	frm.dashboard.add_help ? frm.dashboard.add_help(tooltip) : null;
}

async function select_payment_account(frm) {
	const result = await frappe.db.get_value(
		"Purchase Invoice",
		frm.doc.purchase_invoice,
		"company",
	);
	const company = result?.message?.company;
	if (!company) {
		frappe.throw(__("Unable to resolve the Purchase Invoice company."));
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Record Payment"),
		fields: [
			{
				fieldname: "bank_account",
				fieldtype: "Link",
				label: __("Cash or Bank Account"),
				options: "Account",
				reqd: 1,
				get_query: () => ({
					filters: {
						company,
						is_group: 0,
						disabled: 0,
						account_type: ["in", ["Cash", "Bank"]],
					},
				}),
			},
		],
		primary_action_label: __("Create Payment Entry"),
		primary_action(values) {
			dialog.hide();
			frm.call("make_payment_entry", { bank_account: values.bank_account }).then((response) => {
				const payment_entry = frappe.model.sync(response.message)[0];
				frappe.set_route("Form", payment_entry.doctype, payment_entry.name);
			});
		},
	});
	dialog.show();
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
