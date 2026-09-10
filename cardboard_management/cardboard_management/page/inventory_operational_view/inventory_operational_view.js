frappe.pages["inventory-operational-view"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("المخزون"),
		single_column: true,
	});
	const state = { selected_item: null, selected_date: null, data: null, request_id: 0 };
	const malformedEgpSymbol = "£ or ج.م";
	const EMPTY = {
		no_stock: "لا يوجد مخزون متاح في هذا التاريخ.",
		no_activity: "لا توجد حركات مسجلة في هذا اليوم.",
		no_supplies: "لا توجد توريدات في هذا اليوم.",
		no_sales: "لا توجد عمليات بيع في هذا اليوم.",
	};

	page.main.addClass("cm-inventory-operational-view").attr("dir", "rtl");
	page.set_title_sub(__("متابعة المخزون وحركة التوريد والبيع"));
	page.set_primary_action(__("+ تسجيل بيع"), () => frappe.new_doc("Cardboard Sale"));
	page.add_action_item(__("تحديث"), () => load());
	page.add_action_item(__("عرض التفاصيل"), () => showDetails());
	page.add_action_item(__("عرض توريدات اليوم"), () => showSupplies());
	page.add_action_item(__("عرض مبيعات اليوم"), () => showSales());

	function escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	function currency(value, currencyCode) {
		return frappe
			.format(value ?? 0, { fieldtype: "Currency", options: currencyCode })
			.replaceAll(malformedEgpSymbol, "ج.م");
	}

	function number(value, precision) {
		return `<bdi class="cm-inventory-number">${frappe.format(value ?? 0, {
			fieldtype: "Float",
			precision: precision ?? 3,
		})}</bdi>`;
	}

	function metric(value, uom) {
		return `${number(value)} <bdi class="cm-inventory-unit">${escape(uom || "Kg")}</bdi>`;
	}

	function emptyState(message, extraClass = "") {
		return `<div class="cm-inventory-empty-state ${extraClass}">
			<span class="cm-inventory-empty-icon" aria-hidden="true">—</span>
			<strong>${escape(message)}</strong>
		</div>`;
	}

	function hasActivity(record) {
		return Boolean(record && (Number(record.count) > 0 || Number(record.quantity) > 0));
	}

	function activityRecord(activity, name) {
		return (activity && activity[name]) || { count: 0, quantity: 0 };
	}

	function dateContext(data) {
		const isToday = data.is_today ?? data.selected_date === frappe.datetime.nowdate();
		if (isToday) {
			return {
				heading: "المخزون الحالي",
				caption: "الرصيد المعتمد حتى الآن",
			};
		}
		return {
			heading: `رصيد المخزون في نهاية يوم ${escape(data.selected_date)}`,
			caption: "لقطة نهاية اليوم من رصيد المخزون",
		};
	}

	function listRoute() {
		const filters = { posting_date: state.data.selected_date, warehouse: state.data.warehouse };
		if (state.selected_item) filters.item = state.selected_item;
		return filters;
	}

	function showSupplies() {
		if (state.data) frappe.set_route("List", "Cardboard Supply", listRoute());
	}

	function showSales() {
		if (state.data) frappe.set_route("List", "Cardboard Sale", listRoute());
	}

	function showDetails() {
		if (!state.data) return;
		frappe.set_route("query-report", "Stock Balance", {
			company: state.data.company,
			warehouse: state.data.warehouse,
			item_group: state.data.cardboard_item_group,
		});
	}

	function renderHeader(data) {
		const context = dateContext(data);
		return `
			<header class="cm-inventory-header">
				<div class="cm-inventory-header-copy">
					<span class="cm-inventory-eyebrow">إدارة المخزن</span>
					<h1>المخزون</h1>
					<p>متابعة المخزون وحركة التوريد والبيع</p>
				</div>
				<div class="cm-inventory-header-actions">
					<button type="button" class="btn btn-primary cm-inventory-sale-action">+ تسجيل بيع</button>
					<button type="button" class="btn btn-default cm-inventory-page-refresh">تحديث</button>
				</div>
			</header>
			<div class="cm-inventory-stock-context" role="status">
				<strong>${context.heading}</strong>
				<span>${context.caption}</span>
			</div>`;
	}

	function renderFilters(data) {
		const options = [`<option value="">كل الأنواع</option>`]
			.concat(
				(data.items || []).map((item) => {
					const selected = item.name === state.selected_item ? " selected" : "";
					return `<option value="${escape(item.name)}"${selected}>${escape(item.item_name || item.name)}</option>`;
				})
			)
			.join("");

		return `
			<section class="cm-inventory-filter-panel" aria-label="مرشحات المخزون">
				<div class="cm-inventory-filter-toolbar">
					<div class="cm-inventory-context cm-inventory-context-badges">
						<div class="cm-inventory-context-badge">
							<span>الشركة</span><strong>${escape(data.company)}</strong>
						</div>
						<div class="cm-inventory-context-badge">
							<span>المخزن</span><strong>${escape(data.warehouse_name)}</strong>
						</div>
					</div>
					<div class="cm-inventory-filter-controls">
						<div class="cm-inventory-field">
							<label for="cm-cardboard-item">نوع الكرتون</label>
							<select id="cm-cardboard-item" class="form-control">${options}</select>
						</div>
						<div class="cm-inventory-field cm-inventory-date-field">
							<label for="cm-inventory-date">التاريخ</label>
							<div class="cm-inventory-date-control">
								<input id="cm-inventory-date" class="form-control" data-fieldtype="Date" type="text" value="${escape(data.selected_date)}" readonly>
								<button type="button" class="btn btn-default cm-inventory-today">اليوم</button>
							</div>
						</div>
					</div>
				</div>
			</section>`;
	}

	function renderKpis(data) {
		const summary = data.summary || {};
		const activity = data.activity || {};
		const uom = summary.uom || "Kg";
		const supplies = activityRecord(activity, "supplies");
		const sales = activityRecord(activity, "sales");
		const quantity = summary.quantity === null || summary.quantity === undefined
			? "—"
			: metric(summary.quantity, uom);

		return `
			<section class="cm-inventory-kpi-grid" aria-label="مؤشرات المخزون">
				<article class="cm-inventory-kpi cm-inventory-kpi-stock">
					<span class="cm-inventory-kpi-label">إجمالي المخزون</span>
					<strong class="cm-inventory-kpi-value">${quantity}</strong>
					<small>الرصيد المتاح</small>
				</article>
				<article class="cm-inventory-kpi cm-inventory-kpi-value-card">
					<span class="cm-inventory-kpi-label">قيمة المخزون</span>
					<strong class="cm-inventory-kpi-value"><bdi class="cm-inventory-number">${currency(data.summary?.stock_value, data.currency)}</bdi></strong>
					<small>بالعملة المحلية <bdi>ج.م</bdi></small>
				</article>
				<article class="cm-inventory-kpi cm-inventory-kpi-inbound">
					<span class="cm-inventory-kpi-label">توريدات اليوم</span>
					<strong class="cm-inventory-kpi-value">${metric(supplies.quantity, uom)}</strong>
					<small><bdi>${supplies.count || 0}</bdi> عملية</small>
				</article>
				<article class="cm-inventory-kpi cm-inventory-kpi-outbound">
					<span class="cm-inventory-kpi-label">مبيعات اليوم</span>
					<strong class="cm-inventory-kpi-value">${metric(sales.quantity, uom)}</strong>
					<small><bdi>${sales.count || 0}</bdi> عملية</small>
				</article>
			</section>`;
	}

	function renderCards(data) {
		const rows = data.rows || [];
		const uom = (data.summary && data.summary.uom) || "Kg";
		if (!rows.length) {
			return `<div class="cm-inventory-cards">${emptyState(EMPTY.no_stock)}</div>`;
		}

		return `<div class="cm-inventory-cards">
			${rows
				.map(
					(row) => `
					<article class="cm-inventory-card" data-item-code="${escape(row.item_code)}">
						<header class="cm-inventory-card-header">
							<div>
								<h3>${escape(row.item_name)}</h3>
								<p class="cm-inventory-code"><bdi>${escape(row.item_code)}</bdi></p>
							</div>
							<span class="cm-inventory-uom">${escape(row.stock_uom || uom)}</span>
						</header>
						<div class="cm-inventory-quantity">
							<span>المتاح</span>
							<strong>${metric(row.quantity, row.stock_uom || uom)}</strong>
						</div>
						<div class="cm-inventory-card-stats">
							<div class="cm-inventory-value">
								<span>قيمة المخزون</span>
								<strong><bdi class="cm-inventory-number">${currency(row.stock_value, data.currency)}</bdi></strong>
							</div>
							<div class="cm-inventory-rate">
								<span>متوسط قيمة الوحدة</span>
								<strong><bdi class="cm-inventory-number">${currency(row.quantity ? row.stock_value / row.quantity : 0, data.currency)}</bdi> / <bdi>${escape(row.stock_uom || uom)}</bdi></strong>
							</div>
						</div>
						<footer class="cm-inventory-item-movement">
							<span class="cm-inventory-movement-title">حركة اليوم</span>
							<div class="cm-inventory-movement-grid">
								<div class="cm-inventory-movement-metric cm-inventory-inbound">
									<span>توريد اليوم</span>
									<strong data-item-activity="supplies">—</strong>
								</div>
								<div class="cm-inventory-movement-metric cm-inventory-outbound">
									<span>بيع اليوم</span>
									<strong data-item-activity="sales">—</strong>
								</div>
							</div>
						</footer>
					</article>`
				)
				.join("")}
		</div>`;
	}

	function renderActivityCard(label, record, uom, emptyMessage, tone) {
		return `
			<article class="cm-inventory-activity-card ${tone}">
				<span>${label}</span>
				<strong>${metric(record.quantity, uom)}</strong>
				<small><bdi>${record.count || 0}</bdi> عملية</small>
				${hasActivity(record) ? "" : `<em>${escape(emptyMessage)}</em>`}
			</article>`;
	}

	function renderActivity(data) {
		const activity = data.activity || {};
		const uom = (data.summary && data.summary.uom) || "Kg";
		const supplies = activityRecord(activity, "supplies");
		const sales = activityRecord(activity, "sales");
		const hasMovement = hasActivity(supplies) || hasActivity(sales);
		const net = Number(activity.net || 0);
		const movementHeading = (data.is_today ?? data.selected_date === frappe.datetime.nowdate())
			? "حركة اليوم"
			: `حركة يوم ${escape(data.selected_date)}`;

		return `
			<section class="cm-inventory-activity">
				<div class="cm-inventory-section-heading">
					<div><span class="cm-inventory-eyebrow">الحركة التشغيلية</span><h2>${movementHeading}</h2></div>
					<span class="cm-inventory-date-badge"><bdi>${escape(data.selected_date)}</bdi></span>
				</div>
				<div class="cm-inventory-activity-grid">
					${renderActivityCard("توريدات", supplies, uom, EMPTY.no_supplies, "cm-inventory-activity-inbound")}
					${renderActivityCard("مبيعات", sales, uom, EMPTY.no_sales, "cm-inventory-activity-outbound")}
					<article class="cm-inventory-activity-card cm-inventory-activity-net">
						<span>صافي الحركة</span>
						<strong>${metric(net, uom)}</strong>
						<small>التوريد ناقص البيع</small>
					</article>
				</div>
				${hasMovement ? "" : emptyState(EMPTY.no_activity, "cm-inventory-activity-empty")}
				<div class="cm-inventory-activity-actions">
					<button type="button" class="btn btn-default cm-inventory-supplies-action">عرض توريدات اليوم</button>
					<button type="button" class="btn btn-default cm-inventory-sales-action">عرض مبيعات اليوم</button>
				</div>
			</section>`;
	}

	function render(data) {
		state.data = data;
		page.main.html(`
			<section class="cm-inventory-shell">
				${renderHeader(data)}
				${renderFilters(data)}
				<section class="cm-inventory-stock-section">
					<div class="cm-inventory-section-heading cm-inventory-stock-heading">
						<div><span class="cm-inventory-eyebrow">نظرة سريعة</span><h2>${dateContext(data).heading}</h2></div>
						<button type="button" class="btn btn-default cm-inventory-details-action">عرض تفاصيل المخزون</button>
					</div>
					${renderKpis(data)}
					${renderCards(data)}
				</section>
				${renderActivity(data)}
				<section class="cm-inventory-secondary-actions">
					<div><span class="cm-inventory-eyebrow">تفاصيل إضافية</span><h2>مراجع المخزون</h2></div>
					<button type="button" class="btn btn-default cm-inventory-details-action">عرض تفاصيل المخزون</button>
				</section>
			</section>`);

		bindActions();
		setupDatePicker(data);
		hydrateItemActivity(data);
	}

	function bindActions() {
		page.main.find(".cm-inventory-sale-action").on("click", () => frappe.new_doc("Cardboard Sale"));
		page.main.find(".cm-inventory-page-refresh").on("click", () => load());
		page.main.find(".cm-inventory-details-action").on("click", () => showDetails());
		page.main.find(".cm-inventory-supplies-action").on("click", () => showSupplies());
		page.main.find(".cm-inventory-sales-action").on("click", () => showSales());
		page.main.find("#cm-cardboard-item").on("change", function () {
			state.selected_item = this.value || null;
			load();
		});
		page.main.find(".cm-inventory-today").on("click", () => {
			state.selected_date = null;
			load();
		});
	}

	function setupDatePicker() {
		const $input = page.main.find("#cm-inventory-date");
		$input.datepicker({
			language: "ar",
			autoClose: true,
			todayButton: true,
			todayHighlight: true,
			maxDate: new Date(),
			dateFormat: "yyyy-mm-dd",
			onSelect(dateText) {
				state.selected_date = dateText;
				load();
			},
		});
	}

	function applyItemActivity(itemCode, activity, uom) {
		const $card = page.main.find(".cm-inventory-card").filter(function () {
			return $(this).attr("data-item-code") === itemCode;
		});
		if (!$card.length) return;
		const supplies = activityRecord(activity, "supplies");
		const sales = activityRecord(activity, "sales");
		$card.find('[data-item-activity="supplies"]').html(metric(supplies.quantity, uom));
		$card.find('[data-item-activity="sales"]').html(metric(sales.quantity, uom));
	}

	function hydrateItemActivity(data) {
		const rows = data.rows || [];
		if (!rows.length) return;
		const uom = (data.summary && data.summary.uom) || "Kg";
		if (state.selected_item && data.activity) {
			applyItemActivity(state.selected_item, data.activity, uom);
			return;
		}
		rows.forEach((row) => {
			frappe.call({
				method: "cardboard_management.inventory.get_inventory_overview",
				args: { item_code: row.item_code, selected_date: data.selected_date },
				callback: (response) => {
					if (state.data === data) {
						applyItemActivity(row.item_code, response.message?.activity, row.stock_uom || uom);
					}
				},
			});
		});
	}

	function renderError(message) {
		page.main.html(`<section class="cm-inventory-shell"><div class="cm-inventory-empty-state cm-inventory-error">${escape(message)}</div></section>`);
	}

	function load() {
		const requestId = ++state.request_id;
		page.main.html('<div class="cm-inventory-loading">جارٍ تحديث المخزون…</div>');
		frappe.call({
			method: "cardboard_management.inventory.get_inventory_overview",
			args: { item_code: state.selected_item, selected_date: state.selected_date },
			callback: (response) => {
				if (requestId === state.request_id) render(response.message);
			},
			error: (response) => {
				if (requestId === state.request_id) {
					renderError(response?.message || "تعذر تحميل المخزون. يرجى المحاولة مرة أخرى.");
				}
			},
		});
	}

	load();
};
