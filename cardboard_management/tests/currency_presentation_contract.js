const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const formHandlers = {};
const classes = new Set();
const document = {
	readyState: "complete",
	body: { classList: { toggle: (name, enabled) => (enabled ? classes.add(name) : classes.delete(name)) } },
	documentElement: { getAttribute: () => "rtl" },
	createTreeWalker: () => ({ nextNode: () => false }),
};
const nativeCurrencyInputs = [];
const window = {
	frappe: {
		boot: { lang: "ar" },
		get_route: () => ["Form", "Cardboard Supply", "SUP-0001"],
		meta: { get_field_currency: () => "EGP" },
		form: {
			formatters: {
				Currency: (value) => {
					nativeCurrencyInputs.push(value);
					return `£ or ج.م ${value.toFixed(2)}`;
				},
			},
		},
		ui: {
			form: {
				on: (doctype, handlers) => {
					const existing = formHandlers[doctype] || {};
					formHandlers[doctype] = {
						...existing,
						...handlers,
						refresh: (frm) => {
							existing.refresh?.(frm);
							handlers.refresh?.(frm);
						},
					};
				},
			},
		},
		router: { on: () => {} },
		utils: { is_rtl: () => true },
	},
	addEventListener: () => {},
};
const context = {
	window,
	document,
	Node: { TEXT_NODE: 3, ELEMENT_NODE: 1 },
	NodeFilter: { SHOW_TEXT: 4 },
	MutationObserver: class { observe() {} disconnect() {} },
	requestAnimationFrame: (fn) => fn(),
	__: (value) => value,
};
vm.runInNewContext(fs.readFileSync(process.argv[2], "utf8"), context);

function form(doctype, fieldnames) {
	const fields_dict = Object.fromEntries(fieldnames.map((fieldname) => [fieldname, { df: { fieldtype: "Currency", fieldname } }]));
	const refreshed = [];
	return {
		doctype,
		doc: { docstatus: 0 },
		page: { set_primary_action: () => {} },
		savesubmit: () => {},
		fields_dict,
		refresh_field: (fieldname) => refreshed.push(fieldname),
		refreshed,
	};
}

const supply = form("Cardboard Supply", ["rate_per_kg", "total_amount"]);
formHandlers["Cardboard Supply"].refresh(supply);
assert.deepStrictEqual(supply.refreshed, ["rate_per_kg", "total_amount"]);
assert.strictEqual(supply.fields_dict.total_amount.df.formatter(5200, supply.fields_dict.total_amount.df), "ج.م 5200.00");
assert.strictEqual(supply.fields_dict.rate_per_kg.df.formatter(6.5, supply.fields_dict.rate_per_kg.df), "ج.م 6.50");

const payment = form("Cardboard Supplier Payment", ["amount"]);
formHandlers["Cardboard Supplier Payment"].refresh(payment);
assert.strictEqual(payment.fields_dict.amount.df.formatter(3000, payment.fields_dict.amount.df), "ج.م 3000.00");

const quickExpense = form("Quick Expense", ["amount"]);
formHandlers["Quick Expense"].refresh(quickExpense);
assert.strictEqual(quickExpense.fields_dict.amount.df.formatter(42, quickExpense.fields_dict.amount.df), "ج.م 42.00");

assert.deepStrictEqual(nativeCurrencyInputs, [5200, 6.5, 3000, 42]);
assert.strictEqual(formHandlers["Payment Entry"], undefined);
console.log("currency presentation contract: ok");
