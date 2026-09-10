frappe.pages["inventory-operational-view"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("المخزون الحالي"),
		single_column: true,
	});
	const state = { selected_item: null, data: null };
	const malformedEgpSymbol = "£ or ج.م";

	page.main.addClass("cm-inventory-operational-view").attr("dir", "rtl");
	page.set_primary_action(__("تحديث"), () => load());
	page.add_action_item(__("عرض التفاصيل"), () => {
		if (!state.data) return;
		frappe.set_route("query-report", "Stock Balance", {
			company: state.data.company,
			warehouse: state.data.warehouse,
			item_group: state.data.cardboard_item_group,
		});
	});

	function escape(value) {
		return frappe.utils.escape_html(String(value || ""));
	}

	function currency(value, currencyCode) {
		return frappe.format(value || 0, { fieldtype: "Currency", options: currencyCode })
			.replaceAll(malformedEgpSymbol, "ج.م");
	}

	function renderError(message) {
		page.main.html(`<div class="cm-inventory-empty">${escape(message)}</div>`);
	}

	function render(data) {
		state.data = data;
		if (data.state === "no_items") {
			renderError("لا توجد أصناف كرتون متاحة في إعدادات إدارة الكرتون.");
			return;
		}
		if (data.state === "no_stock") {
			renderError("لا يوجد مخزون كرتون متاح حالياً.");
			return;
		}

		const options = ["<option value=\"\">كل الأنواع</option>"]
			.concat((data.items || []).map((item) => {
				const selected = item.name === state.selected_item ? " selected" : "";
				return `<option value="${escape(item.name)}"${selected}>${escape(item.item_name || item.name)}</option>`;
			})).join("");
		const cards = (data.rows || []).map((row) => `
			<article class="cm-inventory-card">
				<header class="cm-inventory-card-header">
					<h3>${escape(row.item_name)}</h3>
					<span class="cm-inventory-uom">${escape(row.stock_uom)}</span>
				</header>
				<div class="cm-inventory-quantity"><bdi class="cm-inventory-number">${frappe.format(row.quantity, { fieldtype: "Float", precision: 3 })}</bdi></div>
				<div class="cm-inventory-value"><span>القيمة</span><bdi class="cm-inventory-number">${currency(row.stock_value, data.currency)}</bdi></div>
			</article>`).join("");
		const quantitySummary = data.summary.quantity === null
			? "لا يمكن جمع الكميات لاختلاف وحدات القياس."
			: `<bdi class="cm-inventory-number">${frappe.format(data.summary.quantity, { fieldtype: "Float", precision: 3 })} ${escape(data.summary.uom)}</bdi>`;

		page.main.html(`
			<section class="cm-inventory-shell">
				<div class="cm-inventory-toolbar">
					<label for="cm-cardboard-item">نوع الكرتون</label>
					<select id="cm-cardboard-item" class="form-control">${options}</select>
				</div>
				<div class="cm-inventory-context-badges">
					<div class="cm-inventory-context-badge"><span>الشركة</span><strong>${escape(data.company)}</strong></div>
					<div class="cm-inventory-context-badge"><span>المخزن</span><strong>${escape(data.warehouse_name)}</strong></div>
				</div>
				<div class="cm-inventory-cards">${cards}</div>
				<section class="cm-inventory-summary">
					<div class="cm-inventory-summary-item"><span class="cm-inventory-summary-label">إجمالي الوزن</span><strong class="cm-inventory-summary-value">${quantitySummary}</strong></div>
					<div class="cm-inventory-summary-item"><span class="cm-inventory-summary-label">إجمالي القيمة</span><strong class="cm-inventory-summary-value"><bdi class="cm-inventory-number">${currency(data.summary.stock_value, data.currency)}</bdi></strong></div>
				</section>
			</section>`);
		page.main.find("#cm-cardboard-item").on("change", function () {
			state.selected_item = this.value || null;
			load();
		});
	}

	function load() {
		page.main.html('<div class="cm-inventory-loading">جارٍ تحديث المخزون…</div>');
		frappe.call({
			method: "cardboard_management.inventory.get_inventory_overview",
			args: { item_code: state.selected_item },
			callback: (response) => render(response.message),
			error: (response) => renderError(response?.message || "تعذر تحميل المخزون. يرجى المحاولة مرة أخرى."),
		});
	}

	load();
};
