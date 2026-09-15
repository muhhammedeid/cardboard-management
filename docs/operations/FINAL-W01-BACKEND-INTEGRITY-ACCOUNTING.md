# FINAL-W01 — Backend Integrity & Accounting Lifecycle

## Decision: stock and settlement weight semantics

`net_weight` is the physical quantity received into inventory.

`payable_weight` is used only to calculate supplier settlement after the approved
weight discount:

```text
net_weight     = gross_weight - tare_weight
payable_weight = net_weight - discount_weight
total_amount   = payable_weight × rate_per_kg
```

The linked ERPNext Purchase Invoice posts `net_weight` as its stock quantity. Its
financial total equals `total_amount`; its effective item rate is normalized
against physical `net_weight` so the native Stock Ledger remains physically
correct while ERPNext Accounts Payable reflects the discounted supplier value.

Do not post `payable_weight` to the Stock Ledger. Reports that show physical stock
or movement must label/use `net_weight`; supplier settlement and payable reports
must label/use `payable_weight` or `total_amount` as appropriate.

## Payment lifecycle contract

Cardboard Supplier Payment owns one linked standard ERPNext Payment Entry. The
wrapper does not write Purchase Invoice outstanding amounts, Payment Ledger rows,
GL Entries, or supplier balances. On submit it locks the wrapper row, reuses an
existing linked Payment Entry on retry, allocates only submitted open supplier
Purchase Invoices in FIFO order, and validates mapping before and after native
submit. Cancellation cancels that linked Payment Entry first so ERPNext restores
outstanding balances.

Required observable sequence:

```text
Invoice 100 → partial payment 10 → outstanding 90
retry same wrapper → outstanding remains 90; no second Payment Entry
final payment 90 → outstanding 0
```

## Test-isolation rule

Lifecycle tests use a new supplier and assert native-voucher-scoped stock/ledger
rows or per-fixture deltas. They must never assert an absolute site-wide inventory
balance, because operational baseline stock is not test fixture data.
