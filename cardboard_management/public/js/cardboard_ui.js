(function () {
	"use strict";

	const NAVIGATION = Object.freeze([
		{ label: "الرئيسية", name: "home", route: "Workspaces/Cardboard Management", group: "primary" },
		{ label: "التوريدات", name: "supply", route: "List/Cardboard Supply", group: "primary" },
		{ label: "المبيعات", name: "sale", route: "List/Cardboard Sale", group: "primary" },
		{ label: "الموردون", name: "supplier", route: "List/Supplier", group: "primary" },
		{ label: "المدفوعات", name: "payment", route: "List/Cardboard Supplier Payment", group: "primary" },
		{ label: "المصروفات", name: "expense", route: "List/Quick Expense", group: "primary" },
		{ label: "المخزون", name: "inventory", route: "Page/inventory-operational-view", group: "primary" },
		{ label: "التقارير", name: "report", route: "query-report/Stock Balance", group: "primary" },
		{ label: "الإعدادات", name: "settings", route: "Form/Cardboard Dashboard Settings", group: "secondary" },
	]);
	const MALFORMED_EGP_SYMBOL = "£ or ج.م";

	function escapeHtml(value) {
		return window.frappe?.utils?.escape_html
			? window.frappe.utils.escape_html(String(value ?? ""))
			: String(value ?? "").replace(/[&<>"']/g, (character) => ({
				"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
			}[character]));
	}

	function format(value, options) {
		return window.frappe?.format ? window.frappe.format(value, options) : String(value ?? "—");
	}

	// Frappe display formatters can return raw markup or markup escaped by a
	// surrounding renderer. Decode at most three times in detached elements,
	// then keep only the final plain display value.
	function normalizeDisplayText(value) {
		let text = String(value ?? "");
		for (let pass = 0; pass < 3; pass += 1) {
			const holder = document.createElement("span");
			holder.innerHTML = text;
			const next = holder.textContent || "";
			if (next === text) break;
			text = next;
		}
		return text
			.replace(/<\/?[a-z][^>]*>/gi, "")
			.replace(/&lt;\/?[a-z][^&]*&gt;/gi, "")
			.replace(/\s+/g, " ")
			.trim();
	}

	function formatDisplayText(value, options) {
		const formatted = options ? format(value, options) : String(value ?? "—");
		return normalizeDisplayText(formatted)
			.replaceAll(MALFORMED_EGP_SYMBOL, "ج.م");
	}

	// Formatters return plain text. Rendering is a separate DOM-owned contract:
	// create one bidi node and assign the final display value through textContent.
	function createBidiValue(value, className = "cm-number") {
		const node = document.createElement("bdi");
		node.setAttribute("dir", "ltr");
		node.className = className;
		node.textContent = String(value ?? "—");
		return node;
	}

	function renderBidiValue(root, selector, value, className = "cm-number") {
		const slot = root?.querySelector(selector);
		if (!slot) return null;
		const node = createBidiValue(value, className);
		slot.replaceWith(node);
		return node;
	}

	function ltr(value, className = "cm-number") {
		return createBidiValue(formatDisplayText(value), className);
	}

	function formatCurrency(value, currency) {
		return formatDisplayText(value, { fieldtype: "Currency", options: currency });
	}

	function formatQuantity(value, uom) {
		const quantity = formatDisplayText(value, { fieldtype: "Float" });
		const unit = formatDisplayText(uom || "");
		return `${quantity} ${unit}`.trim();
	}

	function formatCode(value) {
		return formatDisplayText(value);
	}

	function icon(name) {
		return `<span class="cm-nav-icon" aria-hidden="true">${escapeHtml(name).slice(0, 1).toUpperCase()}</span>`;
	}

	function navItem(item, active) {
		return `<li><a class="cm-nav-item" href="#${item.route}" data-cm-route="${escapeHtml(item.route)}" data-cm-nav-name="${escapeHtml(item.name)}"${active === item.name ? ' aria-current="page"' : ""}>${icon(item.name)}<span class="cm-nav-item__label">${escapeHtml(item.label)}</span></a></li>`;
	}

	function renderNavigation(active) {
		return NAVIGATION.reduce((groups, item) => {
			(groups[item.group] ||= []).push(navItem(item, active));
			return groups;
		}, { primary: [], secondary: [] });
	}

	function navigationMarkup(active) {
		const groups = renderNavigation(active);
		return `<ul class="cm-nav-list" data-cm-nav-group="primary">${groups.primary.join("")}</ul><div class="cm-nav-spacer"></div><ul class="cm-nav-list" data-cm-nav-group="secondary">${groups.secondary.join("")}</ul>`;
	}

	function mountAppShell(root, options = {}) {
		if (!root) return null;
		const active = options.active || "home";
		const context = options.context
			? `<span class="cm-context-chip" data-cm-context>${escapeHtml(options.context)}</span>`
			: `<span class="cm-context-chip" data-cm-context hidden></span>`;
		root.classList.add("cm-app");
		root.setAttribute("dir", "rtl");
		root.innerHTML = `<div class="cm-app-shell"><aside class="cm-nav-rail" aria-label="التنقل الرئيسي"><div class="cm-brand"><span class="cm-brand__mark" aria-hidden="true">ك</span><span class="cm-brand__copy"><span class="cm-brand__title">إدارة الكرتون</span><span class="cm-brand__sub">CARDBOARD OPS</span></span></div>${navigationMarkup(active)}<div class="cm-nav-footer"><span class="cm-connection-dot"></span>النظام متصل</div></aside><main class="cm-app-main"><header class="cm-topbar"><div class="cm-topbar__start"><button class="cm-icon-button cm-topbar__menu" type="button" aria-label="فتح القائمة" data-cm-open-navigation>☰</button><strong class="cm-topbar__title">${escapeHtml(options.topbarTitle || "إدارة الكرتون")}</strong></div><div class="cm-topbar__end">${context}<button class="cm-button cm-button--primary" type="button" data-cm-quick-action>إجراء جديد</button><button class="cm-icon-button" type="button" aria-label="الحساب">◉</button></div></header><section class="cm-page-frame" data-cm-page-frame></section></main></div>`;
		root.querySelectorAll("[data-cm-route]").forEach((link) => link.addEventListener("click", (event) => {
			event.preventDefault();
			options.onNavigate?.(link.dataset.cmRoute);
		}));
		root.querySelector("[data-cm-quick-action]")?.addEventListener("click", () => createQuickAction(root, options));
		root.querySelector("[data-cm-open-navigation]")?.addEventListener("click", () => createNavigationDrawer(root, {
			active,
			onNavigate: options.onNavigate,
		}));
		return root.querySelector("[data-cm-page-frame]");
	}

	function createPageFrame(frame, options = {}) {
		if (!frame) return null;
		const crumb = options.breadcrumb?.length
			? `<nav class="cm-breadcrumb" aria-label="مسار الصفحة">${options.breadcrumb.map(escapeHtml).join(" / ")}</nav>`
			: "";
		const context = options.context ? `<span class="cm-context-chip">${escapeHtml(options.context)}</span>` : "";
		frame.innerHTML = `${crumb}<header class="cm-page-header"><div class="cm-page-header__copy"><h1 class="cm-page-title">${escapeHtml(options.title || "")}</h1>${options.subtitle ? `<p class="cm-page-subtitle">${escapeHtml(options.subtitle)}</p>` : ""}${context}</div><div class="cm-page-actions">${options.actions || ""}</div></header><div data-cm-page-body></div>`;
		return frame.querySelector("[data-cm-page-body]");
	}

	function createQuickAction(root, options = {}) {
		const existing = root.querySelector("[data-cm-quick-overlay]");
		if (existing) return existing.remove();
		const overlay = document.createElement("div");
		overlay.className = "cm-overlay";
		overlay.dataset.cmQuickOverlay = "true";
		overlay.innerHTML = `<section class="cm-dialog" role="dialog" aria-modal="true" aria-labelledby="cm-quick-title"><h2 id="cm-quick-title" class="cm-page-title">إجراء جديد</h2><p class="cm-page-subtitle">اختر العملية التي تريد بدءها.</p><div class="cm-page-actions cm-quick-actions"><button class="cm-button cm-button--primary" data-cm-action="supply">توريدة جديدة</button><button class="cm-button cm-button--secondary" data-cm-action="sale">بيع جديد</button><button class="cm-button cm-button--secondary" data-cm-action="payment">دفعة مورد</button><button class="cm-button cm-button--secondary" data-cm-action="expense">مصروف جديد</button></div><div class="cm-dialog__actions"><button class="cm-button cm-button--ghost" data-cm-close>إغلاق</button></div></section>`;
		root.append(overlay);
		const close = () => overlay.remove();
		overlay.addEventListener("click", (event) => {
			if (event.target === overlay || event.target.closest("[data-cm-close]")) close();
			const action = event.target.closest("[data-cm-action]")?.dataset.cmAction;
			if (action) {
				options.onQuickAction?.(action);
				close();
			}
		});
		overlay.querySelector("button")?.focus();
		return overlay;
	}

	function createDialog(root, options = {}) {
		const overlay = document.createElement("div");
		overlay.className = "cm-overlay";
		overlay.innerHTML = `<section class="cm-dialog" role="dialog" aria-modal="true"><h2 class="cm-page-title">${escapeHtml(options.title || "تأكيد")}</h2><p class="cm-page-subtitle">${escapeHtml(options.message || "")}</p><div class="cm-dialog__actions"><button class="cm-button cm-button--primary" data-cm-confirm>${escapeHtml(options.confirmLabel || "تأكيد")}</button><button class="cm-button cm-button--ghost" data-cm-close>إلغاء</button></div></section>`;
		root.append(overlay);
		overlay.addEventListener("click", (event) => {
			if (event.target === overlay || event.target.closest("[data-cm-close]")) {
				options.onClose?.();
				overlay.remove();
			}
			if (event.target.closest("[data-cm-confirm]")) {
				options.onConfirm?.();
				overlay.remove();
			}
		});
		return overlay;
	}

	function createNavigationDrawer(root, options = {}) {
		const existing = root.querySelector("[data-cm-navigation-overlay]");
		if (existing) return existing;
		const trigger = root.querySelector("[data-cm-open-navigation]");
		const overlay = document.createElement("div");
		overlay.className = "cm-overlay cm-overlay--navigation";
		overlay.dataset.cmNavigationOverlay = "true";
		overlay.innerHTML = `<aside class="cm-drawer cm-navigation-drawer" role="dialog" aria-modal="true" aria-labelledby="cm-navigation-title"><div class="cm-page-header"><h2 id="cm-navigation-title" class="cm-page-title">التنقل</h2><button class="cm-icon-button" data-cm-close aria-label="إغلاق">×</button></div><nav aria-label="التنقل الرئيسي">${navigationMarkup(options.active || "home")}</nav></aside>`;
		root.append(overlay);
		root.classList.add("cm-navigation-open");
		const close = () => {
			overlay.remove();
			root.classList.remove("cm-navigation-open");
			document.removeEventListener("keydown", onKeydown);
			trigger?.focus();
		};
		const onKeydown = (event) => {
			if (event.key === "Escape") close();
		};
		document.addEventListener("keydown", onKeydown);
		overlay.addEventListener("click", (event) => {
			if (event.target === overlay || event.target.closest("[data-cm-close]")) return close();
			const link = event.target.closest("[data-cm-route]");
			if (link) {
				event.preventDefault();
				options.onNavigate?.(link.dataset.cmRoute);
				close();
			}
		});
		overlay.querySelector("[data-cm-close]")?.focus();
		return overlay;
	}
	function createDrawer(root, options = {}) {
		const overlay = document.createElement("div");
		overlay.className = "cm-overlay cm-overlay--drawer";
		overlay.innerHTML = `<aside class="cm-drawer" role="dialog" aria-modal="true"><div class="cm-page-header"><h2 class="cm-page-title">${escapeHtml(options.title || "")}</h2><button class="cm-icon-button" data-cm-close aria-label="إغلاق">×</button></div>${options.body || ""}</aside>`;
		root.append(overlay);
		overlay.addEventListener("click", (event) => {
			if (event.target === overlay || event.target.closest("[data-cm-close]")) overlay.remove();
		});
		return overlay;
	}

	window.CardboardManagementUI = Object.freeze({
		mountAppShell, createPageFrame, createQuickAction, createDialog, createDrawer, createNavigationDrawer,
		navigationMarkup,		formatDisplayText, createBidiValue, renderBidiValue, formatCurrency, formatQuantity,
		formatCode, ltr,
	});
})();
