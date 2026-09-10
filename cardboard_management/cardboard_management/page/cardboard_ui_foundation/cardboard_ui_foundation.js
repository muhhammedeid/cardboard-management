frappe.pages["cardboard-ui-foundation"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "معاينة مكونات التصميم", single_column: true });
	const foundationSurfaceClass = "cardboard-management-foundation-surface";
	const applyFoundationSurface = () => document.body.classList.add(foundationSurfaceClass);
	const clearFoundationSurface = () => document.body.classList.remove(foundationSurfaceClass);
	applyFoundationSurface();
	$(wrapper).on("show", applyFoundationSurface);
	$(wrapper).on("hide", clearFoundationSurface);

	const ui = window.CardboardManagementUI;
	if (!ui) {
		page.main.html(`<section class="cm-error-state"><h2>تعذر تحميل أساس التصميم</h2><p>أعد تحميل الصفحة ثم حاول مرة أخرى.</p></section>`);
		return;
	}

	const frame = ui.mountAppShell(page.main[0], {
		active: "home",
		topbarTitle: "إدارة الكرتون",
		context: "معاينة تطويرية",
	});
	const body = ui.createPageFrame(frame, {
		breadcrumb: ["إدارة الكرتون", "أساس الواجهة"],
		title: "أساس واجهة إدارة الكرتون",
		subtitle: "مراجعة مكونات P04-W01 فقط؛ القيم أدناه أمثلة تنسيق وليست بيانات تشغيلية.",
		context: "معاينة تطويرية",
		actions: `<button class="cm-button cm-button--primary" data-demo-dialog>حوار التأكيد</button><button class="cm-button cm-button--secondary" data-demo-drawer>درج جانبي</button>`,
	});
	body.classList.add("cm-foundation-review");
	body.innerHTML = `<section class="cm-alert-panel"><strong>نطاق المعاينة:</strong> لا توجد اتصالات خلفية أو حسابات أعمال في هذه الصفحة.</section>
	<section class="cm-review-section"><div class="cm-review-section__heading"><h2 class="cm-page-title">الأزرار والحالات</h2><span class="cm-page-subtitle">عناصر تشغيلية مشتركة</span></div><div class="cm-page-actions cm-review-actions"><button class="cm-button cm-button--primary">إجراء رئيسي</button><button class="cm-button cm-button--secondary">إجراء ثانوي</button><button class="cm-button cm-button--ghost">إجراء نصي</button><button class="cm-button cm-button--destructive">إجراء خطِر</button></div><div class="cm-page-actions cm-review-statuses"><span class="cm-status cm-status--draft">مسودة</span><span class="cm-status cm-status--approved">معتمد</span><span class="cm-status cm-status--paid">مدفوع</span><span class="cm-status cm-status--partial">مدفوع جزئيًا</span><span class="cm-status cm-status--unpaid">غير مدفوع</span></div></section>
	<section class="cm-card cm-review-section"><div class="cm-review-section__heading"><h2 class="cm-page-title">الحقول والعرض المعزول</h2><span class="cm-page-subtitle">قيمة العرض من المصدر المعتمد</span></div><div class="cm-review-grid"><label class="cm-field"><span class="cm-field__label">حقل نصي</span><input class="cm-input" placeholder="مثال إدخال" /></label><label class="cm-field"><span class="cm-field__label">قيمة محسوبة من الخادم</span><output class="cm-input cm-field--calculated cm-ltr">—</output></label><div class="cm-field"><span class="cm-field__label">تنسيق قيمة</span><span class="cm-calculated-value cm-input"><span data-cm-value="currency"></span></span></div><div class="cm-field"><span class="cm-field__label">تنسيق وزن</span><span class="cm-calculated-value cm-input"><span data-cm-value="weight"></span></span></div></div></section>
	<section class="cm-review-section"><div class="cm-review-section__heading"><h2 class="cm-page-title">البطاقات وحالات المحتوى</h2><span class="cm-page-subtitle">كثافة مناسبة للمعاينة</span></div><div class="cm-review-grid cm-review-grid--cards"><article class="cm-kpi-card"><span class="cm-kpi-card__label">مؤشر جاهز للربط</span><strong class="cm-kpi-card__value cm-ltr">—</strong><small class="cm-kpi-card__helper">تُعرض القيمة من المصدر المعتمد.</small></article><article class="cm-summary-card"><strong>بطاقة ملخص</strong><p class="cm-page-subtitle">هيكل عرض مشترك بدون بيانات أعمال.</p></article><article class="cm-scale-status"><span class="cm-scale-status__dot"></span>حالة ميزان قابلة لإعادة الاستخدام</article></div></section>
	<section class="cm-card cm-review-section"><div class="cm-review-section__heading"><h2 class="cm-page-title">قائمة متجاوبة</h2><span class="cm-page-subtitle">جدول سطح المكتب وبطاقة الهاتف</span></div><table class="cm-data-table"><thead><tr><th>الهوية</th><th>الحالة</th><th>قيمة معزولة</th><th class="cm-table-actions">إجراء</th></tr></thead><tbody><tr><td><span data-cm-value="table-code"></span></td><td><span class="cm-status cm-status--approved">معتمد</span></td><td><span data-cm-value="table-weight"></span></td><td class="cm-table-actions">عرض</td></tr></tbody></table><article class="cm-record-card cm-review-mobile-record"><div class="cm-record-card__head"><strong><span data-cm-value="record-code"></span></strong><span class="cm-status cm-status--approved">معتمد</span></div><div class="cm-record-card__facts"><span>قيمة معزولة</span><span data-cm-value="record-weight"></span></div></article></section>
	<section class="cm-empty-state cm-foundation-empty"><h2>لا توجد بيانات ضمن الفترة المحددة</h2><p>يوفر هذا المثال بنية الحالة الفارغة فقط.</p><button class="cm-button cm-button--primary">إجراء مرتبط</button></section>`;

	ui.renderBidiValue(body, '[data-cm-value="currency"]', ui.formatCurrency(5200, "EGP"), "cm-number cm-currency");
	ui.renderBidiValue(body, '[data-cm-value="weight"]', ui.formatQuantity(900, "Kg"), "cm-number cm-quantity");
	ui.renderBidiValue(body, '[data-cm-value="table-code"]', ui.formatCode("CARDBOARD-A"), "cm-code");
	ui.renderBidiValue(body, '[data-cm-value="table-weight"]', ui.formatQuantity(900, "Kg"), "cm-number cm-quantity");
	ui.renderBidiValue(body, '[data-cm-value="record-code"]', ui.formatCode("CARDBOARD-A"), "cm-code");
	ui.renderBidiValue(body, '[data-cm-value="record-weight"]', ui.formatQuantity(900, "Kg"), "cm-number cm-quantity");

	page.main.find("[data-demo-dialog]").on("click", () => ui.createDialog(page.main[0], {
		title: "تأكيد تجريبي",
		message: "هذا نمط تأكيد قابل لإعادة الاستخدام ولا ينفذ عملية أعمال.",
	}));
	page.main.find("[data-demo-drawer]").on("click", () => ui.createDrawer(page.main[0], {
		title: "درج تجريبي",
		body: `<p class="cm-page-subtitle">نمط للمرشحات أو السياق، دون بيانات تشغيلية.</p>`,
	}));
};
