frappe.pages["cardboard-ui-foundation"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "معاينة مكونات التصميم", single_column: true });
	page.main.addClass("cm-app").attr("dir", "rtl");
	page.set_title_sub("مرجع تطويري داخلي — لا يمثل شاشة تشغيل أو بيانات أعمال.");

	const ui = window.CardboardManagementUI;
	if (!ui) {
		page.main.html(`<section class="cm-error-state"><h2>تعذر تحميل أساس التصميم</h2><p>أعد تحميل الصفحة ثم حاول مرة أخرى.</p></section>`);
		return;
	}
	const body = ui.createPageFrame(page.main[0], {
		title: "أساس واجهة إدارة الكرتون",
		subtitle: "مراجعة مكونات P04-W01 فقط؛ القيم أدناه أمثلة تنسيق وليست بيانات تشغيلية.",
		context: "معاينة تطويرية",
		actions: `<button class="cm-button cm-button--primary" data-demo-dialog>حوار التأكيد</button><button class="cm-button cm-button--secondary" data-demo-drawer>درج جانبي</button>`,
	});
	body.innerHTML = `<section class="cm-alert-panel"><strong>نطاق المعاينة:</strong> لا توجد اتصالات خلفية أو حسابات أعمال في هذه الصفحة.</section>
	<section style="margin-top:1.5rem"><h2 class="cm-page-title" style="font-size:22px">الأزرار والحالات</h2><div class="cm-page-actions" style="margin-top:1rem"><button class="cm-button cm-button--primary">إجراء رئيسي</button><button class="cm-button cm-button--secondary">إجراء ثانوي</button><button class="cm-button cm-button--ghost">إجراء نصي</button><button class="cm-button cm-button--destructive">إجراء خطِر</button></div><div class="cm-page-actions" style="margin-top:1rem"><span class="cm-status cm-status--draft">مسودة</span><span class="cm-status cm-status--approved">معتمد</span><span class="cm-status cm-status--paid">مدفوع</span><span class="cm-status cm-status--partial">مدفوع جزئيًا</span><span class="cm-status cm-status--unpaid">غير مدفوع</span></div></section>
	<section style="margin-top:1.5rem" class="cm-card"><h2 class="cm-page-title" style="font-size:22px">الحقول والعرض المعزول</h2><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;margin-top:1rem"><label class="cm-field"><span class="cm-field__label">حقل نصي</span><input class="cm-input" placeholder="مثال إدخال" /></label><label class="cm-field"><span class="cm-field__label">قيمة محسوبة من الخادم</span><output class="cm-input cm-field--calculated cm-ltr">—</output></label><div class="cm-field"><span class="cm-field__label">تنسيق قيمة</span><span class="cm-calculated-value cm-input">${ui.formatCurrency(5200, "EGP")}</span></div><div class="cm-field"><span class="cm-field__label">تنسيق وزن</span><span class="cm-calculated-value cm-input">${ui.formatQuantity(900, "Kg")}</span></div></div></section>
	<section style="margin-top:1.5rem"><h2 class="cm-page-title" style="font-size:22px">البطاقات وحالات المحتوى</h2><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem;margin-top:1rem"><article class="cm-kpi-card"><span class="cm-kpi-card__label">مؤشر جاهز للربط</span><strong class="cm-kpi-card__value cm-ltr">—</strong><small class="cm-kpi-card__helper">تُعرض القيمة من المصدر المعتمد.</small></article><article class="cm-summary-card"><strong>بطاقة ملخص</strong><p class="cm-page-subtitle">هيكل عرض مشترك بدون بيانات أعمال.</p></article><article class="cm-scale-status"><span class="cm-scale-status__dot"></span>حالة ميزان قابلة لإعادة الاستخدام</article></div></section>
	<section class="cm-card" style="margin-top:1.5rem"><h2 class="cm-page-title" style="font-size:22px">قائمة متجاوبة</h2><table class="cm-data-table" style="margin-top:1rem"><thead><tr><th>الهوية</th><th>الحالة</th><th>قيمة معزولة</th><th class="cm-table-actions">إجراء</th></tr></thead><tbody><tr><td>${ui.formatCode("CARDBOARD-A")}</td><td><span class="cm-status cm-status--approved">معتمد</span></td><td>${ui.formatQuantity(900,"Kg")}</td><td class="cm-table-actions">عرض</td></tr></tbody></table><article class="cm-record-card" style="margin-top:1rem"><div class="cm-record-card__head"><strong>${ui.formatCode("CARDBOARD-A")}</strong><span class="cm-status cm-status--approved">معتمد</span></div><div class="cm-record-card__facts"><span>قيمة معزولة</span>${ui.formatQuantity(900,"Kg")}</div></article></section>
	<section style="margin-top:1.5rem" class="cm-empty-state"><h2>لا توجد بيانات ضمن الفترة المحددة</h2><p>يوفر هذا المثال بنية الحالة الفارغة فقط.</p><button class="cm-button cm-button--primary">إجراء مرتبط</button></section>`;
	page.main.find("[data-demo-dialog]").on("click", () => ui.createDialog(page.main[0], { title: "تأكيد تجريبي", message: "هذا نمط تأكيد قابل لإعادة الاستخدام ولا ينفذ عملية أعمال." }));
	page.main.find("[data-demo-drawer]").on("click", () => ui.createDrawer(page.main[0], { title: "درج تجريبي", body: `<p class="cm-page-subtitle">نمط للمرشحات أو السياق، دون بيانات تشغيلية.</p>` }));
};
