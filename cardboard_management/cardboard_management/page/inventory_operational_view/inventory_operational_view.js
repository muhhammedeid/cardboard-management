frappe.pages["inventory-operational-view"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("المخزون"),
		single_column: true,
	});
	const state = { selected_item: null, selected_date: null, data: null };
	const malformedEgpSymbol = "£ or ج.م";
	const EMPTY = {
		no_items: "لا توجد أصناف كرتون متاحة في إعدادات إدارة الكرتون.",
		no_stock: "لا يوجد مخزون متاح.",
	};

	page.main.addClass("cm-inventory-operational-view").attr("dir", "rtl");

	page.set_title_sub(__("متابعة المخزون وحركة التوريد والبيع"));
	page.set_primary_action(__("+ تسجيل بيع"), () => frappe.new_doc("Cardboard Sale"));
	page.add_action_item(__("تحديث"), () => load());
	page.add_action_item(__("عرض التفاصيل"), () => {
		if (!state.data) return;
		frappe.set_route("query-report", "Stock Balance", {
			company: state.data.company,
			warehouse: state.data.warehouse,
			item_group: state.data.cardboard_item_group,
		});
	});
	page.add_action_item(__("عرض توريدات اليوم"), () => showSupplies());
	page.add_action_item(__("عرض مبيعات اليوم"), () => showSales());

	function escape(value) {
		return frappe.utils.escape_html(String(value || ""));
	}

	function currency(value, currencyCode) {
		return frappe.format(value || 0, { fieldtype: "Currency", options: currencyCode })
			.replaceAll(malformedEgpSymbol, "ج.م");
	}

	function number(value, precision) {
		return `<bdi class="cm-inventory-number">${frappe.format(value || 0, { fieldtype: "Float", precision: precision ?? 3 })}</bdi>`;
	}

	function listRoute() {
		const filters = {};
		if (state.data) {
			filters.company = state.data.company;
			filters.warehouse = state.data.warehouse;
		}
		if (state.selected_item) filters.item = state.selected_item;
		return filters;
	}

	function showSupplies() {
		frappe.set_route("Form", "List", "Cardboard Supply", listRoute());
	}

	function showSales() {
		frappe.set_route("Form", "List", "Cardboard Sale", listRoute());
	}

	function renderError(message) {
		page.main.html(`<div class="cm-inventory-empty">${escape(message)}</div>`);
	}

	function renderKpis(data) {
		const summary = data.summary || {};
		const activity = data.activity || {};
		const uom = escape(summary.uom || "Kg");
		return `
			<section class="cm-inventory-kpi-grid">
				<div class="cm-inventory-kpi">
					<span class="cm-inventory-kpi-label">إجمالي المخزون</span>
					<strong class="cm-inventory-kpi-value">${summary.quantity === null ? "—" : `${number(summary.quantity)} ${uom}`}</strong>
				</div>
				<div class="cm-inventory-kpi">
					<span class="cm-inventory-kpi-label">قيمة المخزون</span>
					<strong class="cm-inventory-kpi-value"><bdi class="cm-inventory-number">${currency(summary.stock_value, data.currency)}</bdi></strong>
				</div>
				<div class="cm-inventory-kpi">
					<span class="cm-inventory-kpi-label">توريدات اليوم</span>
					<strong class="cm-inventory-kpi-value cm-inventory-in">${activity.supplies ? `${number(activity.supplies.quantity)} ${uom}` : "—"}</strong>
				</div>
				<div class="cm-inventory-kpi">
					<span class="cm-inventory-kpi-label">مبيعات اليوم</span>
					<strong class="cm-inventory-kpi-value cm-inventory-out">${activity.sales ? `${number(activity.sales.quantity)} ${uom}` : "—"}</strong>
				</div>
			</section>`;
	}

	function renderCards(data) {
		const rows = data.rows || [];
		const activity = data.activity || {};
		const byItem = {};
		if (activity.supplies) byItem.supplies = {};
		if (activity.sales) byItem.sales = {};
		return `<div class="cm-inventory-cards">${
			rows.map((row) => `
			<article class="cm-inventory-card">
				<header class="cm-inventory-card-header">
					<h3>${escape(row.item_name)}</h3>
					<span class="cm-inventory-uom">${escape(row.stock_uom)}</span>
				</header>
				<p class="cm-inventory-code">${escape(row.item_code)}</p>
				<div class="cm-inventory-quantity"><span>المتاح</span>${number(row.quantity)}</div>
				<div class="cm-inventory-value"><span>قيمة المخزون</span><bdi class="cm-inventory-number">${currency(row.stock_value, data.currency)}</bdi></div>
				<div class="cm-inventory-rate"><span>متوسط قيمة الوحدة</span><bdi class="cm-inventory-number">${currency(row.quantity ? row.stock_value / row.quantity : 0, data.currency)}</bdi> / ${escape(row.stock_uom)}</div>
			</article>`).join("") || `<div class="cm-inventory-empty">${escape(EMPTY.no_stock)}</div>`
		}</div>`;
	}

	function renderActivity(data) {
		const activity = data.activity || {};
		const uom = escape((data.summary && data.summary.uom) || "Kg");
		if (!activity.supplies && !activity.sales) {
			return `<section class="cm-inventory-activity"><div class="cm-inventory-empty">لا توجد حركات مسجلة في هذا اليوم.</div></section>`;
		}
		return `
			<section class="cm-inventory-activity">
				<header><h4>حركة اليوم</h4><span class="cm-inventory-date-badge">${escape(data.selected_date)}</span></header>
				<div class="cm-inventory-activity-grid">
					<div class="cm-inventory-activity-item">
						<span>توريدات</span>
						<strong>${activity.supplies ? number(activity.supplies.quantity) : "—"} ${uom}</strong>
						<small>${activity.supplies ? activity.supplies.count : 0} عملية</small>
					</div>
					<div class="cm-inventory-activity-item">
						<span>مبيعات</span>
						<strong>${activity.sales ? number(activity.sales.quantity) : "—"} ${uom}</strong>
						<small>${activity.sales ? activity.sales.count : 0} عملية</small>
					</div>
					<div class="cm-inventory-activity-item">
						<span>صافي الحركة</span>
						<strong>${number(activity.net)} ${uom}</strong>
					</div>
				</div>
			</section>`;
	}

	function render(data) {
		state.data = data;
		if (EMPTY[data.state]) {
			renderError(EMPTY[data.state]);
			return;
		}

		const options = [`<option value="">كل الأنواع</option>`]
			.concat((data.items || []).map((item) => {
				const selected = item.name === state.selected_item ? " selected" : "";
				return `<option value="${escape(item.name)}"${selected}>${escape(item.item_name || item.name)}</option>`;
			})).join("");

		page.main.html(`
			<section class="cm-inventory-shell">
				<div class="cm-inventory-toolbar">
					<div class="cm-inventory-filter">
						<label for="cm-cardboard-item">نوع الكرتون</label>
						<select id="cm-cardboard-item" class="form-control">${options}</select>
					</div>
					<div class="cm-inventory-filter">
						<label for="cm-inventory-date">التاريخ</label>
						<input id="cm-inventory-date" class="form-control input-sm" data-fieldtype="Date" type="text" value="${escape(data.selected_date)}">
						<button type="button" class="btn btn-default btn-sm cm-inventory-today">اليوم</button>
					</div>
				</div>
				<div class="cm-inventory-context-badges">
					<div class="cm-inventory-context-badge"><span>الشركة</span><strong>${escape(data.company)}</strong></div>
					<div class="cm-inventory-context-badge"><span>المخزن</span><strong>${escape(data.warehouse_name)}</strong></div>
				</div>
				${renderKpis(data)}
				${renderCards(data)}
				${renderActivity(data)}
			</section>`);

		page.main.find("#cm-cardboard-item").on("change", function () {
			state.selected_item = this.value || null;
			load();
		});
		page.main.find(".cm-inventory-today").on("click", () => {
			state.selected_date = null;
			page.main.find("#cm-inventory-date").val(data.today);
			load();
		});
		setupDatePicker(data);
	}

	function setupDatePicker(data) {
		const $input = page.main.find("#cm-inventory-date");
		$input.datepicker({
			language: "ar",
			autoClose: true,
			todayHighlight: true,
			dateFormat: "yyyy-mm-dd",
			onSelect(dateText) {
				state.selected_date = dateText;
				load();
			},
		});
		$input.attr("readonly", "readonly");
	}

	function load() {
		page.main.html('<div class="cm-inventory-loading">جارٍ تحديث المخزون…</div>');
		frappe.call({
			method: "cardboard_management.inventory.get_inventory_overview",
			args: { item_code: state.selected_item, selected_date: state.selected_date },
			callback: (response) => render(response.message),
			error: (response) => renderError(response?.message || "تعذر تحميل المخزون. يرجى المحاولة مرة أخرى."),
		});
	}

	load();
};
