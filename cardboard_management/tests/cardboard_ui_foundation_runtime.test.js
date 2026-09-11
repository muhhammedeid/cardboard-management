const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function stripMarkup(value) {
	return String(value).replace(/<[^>]*>/g, "");
}

function decodeEntities(value) {
	return String(value).replace(/&(lt|gt|quot|#39|amp);/g, (match, entity) => ({
		lt: "<",
		gt: ">",
		quot: '"',
		"#39": "'",
		amp: "&",
	}[entity]));
}

class FakeElement {
	constructor(tagName) {
		this.tagName = tagName.toUpperCase();
		this.attributes = {};
		this.className = "";
		this.textContent = "";
		this.replacedBy = null;
	}

	set innerHTML(value) {
		this.textContent = decodeEntities(stripMarkup(value));
	}

	setAttribute(name, value) {
		this.attributes[name] = String(value);
	}

	replaceWith(node) {
		this.replacedBy = node;
	}
}

class FakeRoot {
	constructor() {
		this.slots = new Map();
	}

	addSlot(selector) {
		const slot = new FakeElement("span");
		this.slots.set(selector, slot);
		return slot;
	}

	querySelector(selector) {
		return this.slots.get(selector) || null;
	}
}

const sandbox = {
	window: {
		frappe: {
			format(value, options) {
				if (options?.fieldtype === "Currency") {
					return `&lt;div style=&quot;text-align: right&quot;&gt;5,200.00&lt;/div&gt; £ or ج.م`;
				}
				if (options?.fieldtype === "Float") {
					return `<div style="text-align: right">${value}</div>`;
				}
				return String(value);
			},
		},
	},
	document: { createElement: (tagName) => new FakeElement(tagName) },
	console,
};

vm.runInNewContext(
	fs.readFileSync("cardboard_management/public/js/cardboard_ui.js", "utf8"),
	sandbox,
);

const ui = sandbox.window.CardboardManagementUI;
const navigation = ui.navigationMarkup("supply");
assert.strictEqual((navigation.match(/data-cm-nav-name=/g) || []).length, 9);
assert.strictEqual((navigation.match(/data-cm-nav-name="settings"/g) || []).length, 1);
assert(navigation.includes('data-cm-nav-name="supply" aria-current="page"'));
assert(navigation.includes('data-cm-nav-group="primary"'));
assert(navigation.includes('data-cm-nav-group="secondary"'));

const root = new FakeRoot();
const currencySlot = root.addSlot('[data-cm-value="currency"]');
const quantitySlot = root.addSlot('[data-cm-value="weight"]');
const codeSlot = root.addSlot('[data-cm-value="code"]');

ui.renderBidiValue(root, '[data-cm-value="currency"]', ui.formatCurrency(5200, "EGP"), "cm-number cm-currency");
ui.renderBidiValue(root, '[data-cm-value="weight"]', ui.formatQuantity(900, "Kg"), "cm-number cm-quantity");
ui.renderBidiValue(root, '[data-cm-value="code"]', ui.formatCode("CARDBOARD-A"), "cm-code");

for (const [slot, expected] of [
	[currencySlot, "5,200.00 ج.م"],
	[quantitySlot, "900 Kg"],
	[codeSlot, "CARDBOARD-A"],
]) {
	assert(slot.replacedBy, "value slot was not replaced");
	assert.strictEqual(slot.replacedBy.tagName, "BDI");
	assert.strictEqual(slot.replacedBy.attributes.dir, "ltr");
	assert.strictEqual(slot.replacedBy.textContent, expected);
	assert(!/[<&>]/.test(slot.replacedBy.textContent), "markup leaked into visible text");
}

console.log("Foundation review rendering runtime regression: OK");
