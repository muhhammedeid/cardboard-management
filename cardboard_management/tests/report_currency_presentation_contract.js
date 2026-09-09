const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const formHandlers = {};
const routerHandlers = [];
const classes = new Set();
const nativeCurrencyInputs = [];
const nativeReportCalls = [];
const queryReports = {
	"Stock Balance": {
		formatter(value, row, column, data, defaultFormatter) {
			const formatted = defaultFormatter(value, row, column, data);
			return column.fieldname === "out_qty" ? `<span>${formatted}</span>` : formatted;
		},
	},
	"Accounts Payable": {
		formatter(value, row, column, data, defaultFormatter) {
			return data?.bold ? defaultFormatter(value, row, column, data).bold() : defaultFormatter(value, row, column, data);
		},
	},
	"Purchase Register": {},
	"General Ledger": {},
};

class QueryReport {
	constructor(reportName) {
		this.report_name = reportName;
	}

	get_report_settings() {
		nativeReportCalls.push(this.report_name);
		this.report_settings = queryReports[this.report_name];
		return Promise.resolve();
	}
}

const document = {
	readyState: "complete",
	body: { classList: { toggle: (name, enabled) => (enabled ? classes.add(name) : classes.delete(name)) } },
	documentElement: { getAttribute: () => "rtl" },
	createTreeWalker: () => ({ nextNode: () => false }),
};
const window = {
	frappe: {
		boot: { lang: "ar" },
		get_route: () => ["query-report", "Stock Balance"],
		meta: { get_field_currency: () => "EGP" },
		form: { formatters: { Currency: (value) => { nativeCurrencyInputs.push(value); return `£ or ج.م ${value.toFixed(2)}`; } } },
		ui: { form: { on: (doctype, handlers) => { formHandlers[doctype] = handlers; } } },
		views: { QueryReport },
		query_reports: queryReports,
		router: { on: (_event, handler) => routerHandlers.push(handler) },
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

function defaultFormatter(value) {
	return `£ or ج.م ${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

async function formatted(reportName, value, column, data = {}) {
	const report = new QueryReport(reportName);
	await report.get_report_settings();
	return report.report_settings.formatter(value, 0, column, data, defaultFormatter);
}

(async () => {
	const currencyColumn = { fieldtype: "Currency", fieldname: "grand_total" };
	const totalCurrencyColumn = { fieldtype: "Currency", fieldname: "outstanding", isHeader: true };

	assert.strictEqual(await formatted("Stock Balance", 5200, currencyColumn), "ج.م 5,200.00");
	assert.strictEqual(await formatted("Stock Balance", 5200, totalCurrencyColumn), "ج.م 5,200.00");
	assert.strictEqual(await formatted("Accounts Payable", 2200, currencyColumn, { bold: true }), "<b>ج.م 2,200.00</b>");
	assert.strictEqual(await formatted("Purchase Register", 6500, currencyColumn), "ج.م 6,500.00");

	// Refresh uses the same lifecycle and must retain the installed wrapper.
	assert.strictEqual(await formatted("Purchase Register", 3000, currencyColumn), "ج.م 3,000.00");
	assert.deepStrictEqual(nativeReportCalls, ["Stock Balance", "Stock Balance", "Accounts Payable", "Purchase Register", "Purchase Register"]);

	// Formatting stays native except for the exact presentation token on Currency cells.
	assert.strictEqual(await formatted("Stock Balance", 6.5, { fieldtype: "Float", fieldname: "valuation_rate" }), "£ or ج.م 6.50");
	const unrelated = new QueryReport("General Ledger");
	await unrelated.get_report_settings();
	assert.strictEqual(unrelated.report_settings.formatter, undefined);
	assert.strictEqual(defaultFormatter(5200), "£ or ج.م 5,200.00");
	console.log("report currency presentation contract: ok");
})().catch((error) => {
	console.error(error);
	process.exit(1);
});
