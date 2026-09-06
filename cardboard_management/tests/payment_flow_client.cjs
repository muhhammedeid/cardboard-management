const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
let handlers, dialog, route;
const context = {frappe: {
 provide() {}, ui: {form: {on(dt, value) { handlers = value; }},
 Dialog: function(config) {dialog=config; this.show=()=>{}; this.hide=()=>{};}},
 db: {get_value: async()=>({message:{company:"Company selected by invoice"}})},
 model: {sync: doc=>[doc]}, set_route: (...args)=>{route=args;}
}, __:x=>x, flt:Number};
vm.createContext(context);
vm.runInContext(fs.readFileSync("apps/cardboard_management/cardboard_management/cardboard_management/doctype/cardboard_supply/cardboard_supply.js", "utf8"), context);
(async()=>{
 for (const [docstatus, outstanding, expected] of [[0,5525,false],[1,5525,true],[1,3525,true],[1,0,false],[2,5525,false]]) {
  const buttons={};
  const frm={doc:{docstatus,purchase_invoice:"PI",purchase_invoice_outstanding:outstanding},
   toggle_display(){},add_custom_button(label,cb){buttons[label]=cb;},
   call:async(method,args)=>{assert.equal(method,"make_payment_entry"); assert.equal(args.bank_account,"Selected account"); return {message:{doctype:"Payment Entry",name:"new-payment-entry"}};}};
  handlers.refresh(frm);
  assert.equal(Boolean(buttons["Record Payment"]),expected);
  if(expected){await buttons["Record Payment"](); assert.equal(dialog.fields[0].get_query().filters.company,"Company selected by invoice"); dialog.primary_action({bank_account:"Selected account"}); await new Promise(resolve=>setImmediate(resolve)); assert.equal(route.join("/"),"Form/Payment Entry/new-payment-entry");}
 }
 console.log("PASS: button guards, account dialog filter, draft API and native route (mocked Frappe client)");
})().catch(error=>{console.error(error);process.exitCode=1;});
