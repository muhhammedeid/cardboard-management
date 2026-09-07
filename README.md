# Cardboard Management

A custom Frappe v15 app for a small local cardboard recycling and trading ERP.

## Architecture and scope

- **ERPNext remains the ERP engine.**
- **Frappe remains the framework.**
- **cardboard_management contains only business-specific customization and code.**

All custom code belongs in `apps/cardboard_management`. Do not modify
`apps/frappe` or `apps/erpnext`.

The foundation history is documented in `docs/P00-W01.md`. Current business
features are listed below.

## Requirements

- Frappe v15 and ERPNext v15, installed and managed by Bench.
- This foundation was created on Frappe 15.120.0 and ERPNext 15.121.0.
- ERPNext is declared in `required_apps`; this app does not replace ERPNext.

## Current business model

### Cardboard Supply

`Cardboard Supply` records one cardboard Item per transaction, measured in Kg,
against a standard ERPNext Supplier and Warehouse. Physical `net_weight` always
remains gross minus tare. Optional Kg or percentage discounts produce a separate
`payable_weight`, and total amount uses payable weight. Server validation and
calculation are authoritative. The DocType is submittable and uses
`CS-.YYYY.-.#####` naming.

Submitting a Cardboard Supply creates and submits exactly one standard ERPNext
Purchase Invoice with **Update Stock** enabled. The invoice receives physical
`net_weight` as stock quantity while its effective unit rate preserves
`total_amount` as the supplier liability. ERPNext remains authoritative for the
stock ledger, valuation, and GL entries. Cancelling the supply first cancels its
linked Purchase Invoice, reversing those effects. No Purchase Receipt, separate
Stock Entry, or custom GL entry is created.

A submitted supply with an unpaid submitted Purchase Invoice exposes **Record
Payment**. The user selects an enabled Cash or Bank account for the invoice
company, and the custom app asks ERPNext's standard `get_payment_entry` utility
to build an unsaved Payment Entry. ERPNext supplies the payable account and
Purchase Invoice reference; the user may review, reduce the allocation for a
partial payment, save, and submit manually. Cardboard Supply payment status and
outstanding amount are virtual, read-only values derived from the linked Purchase
Invoice on every load; no custom balance or independently maintained payment
status exists.

## Installation and migration

Run from `/home/twenty/frappe/cardboard-bench`, with the existing Bench, Node,
and Yarn toolchain available in the shell:

```bash
bench --site cardboard.localhost install-app cardboard_management
bench --site cardboard.localhost migrate
bench --site cardboard.localhost list-apps
bench start
```

### Local WSL toolchain note

In this environment, Node is loaded by the interactive shell via nvm. The global
Corepack Yarn cache contained an empty `package.json`. Verification used a
bench-local cache instead; no global configuration change is required:

```bash
cd /home/twenty/frappe/cardboard-bench
export COREPACK_HOME=/home/twenty/frappe/cardboard-bench/.cache/corepack
bench start
```

Run this from the existing interactive WSL shell where `node --version` works.
Use the same environment for `bench build --app cardboard_management`.

Installation is a one-time step. Stop any existing development bench before
starting another instance on the same ports.

The app uses the standard Bench-generated package and `modules.txt` declaration.
An idempotent custom-app install/migration hook adds the Purchase Invoice back
reference, configures nine-decimal Purchase Invoice Item rate precision, and
allows Journal Entry rows to reference Quick Expense. Financial amounts still
follow ERPNext/company currency precision. `patches.txt` retains the standard
empty migration sections. All schema extensions and future patches remain
isolated here; core edits and manual database changes are not installation
requirements.

### Local development launchers

The complete environment can be started and stopped with one command each, from
any directory inside WSL:

```bash
cardboard-start   # prepare the environment, then run bench start (foreground)
cardboard-stop    # stop this bench and clean its Redis processes
```

Install once from the app checkout (`scripts/dev/install.sh` symlinks both
commands into `~/.local/bin`, which is already on `$PATH`):

```bash
bash ~/frappe/cardboard-bench/apps/cardboard_management/scripts/dev/install.sh
```

`cardboard-start` validates the bench and site, starts MariaDB only when it is
not running, cleans stale bench Redis processes on ports 13000/11000 (only
processes verified to belong to this bench), and then runs `bench start` in
the foreground. `Ctrl+C` remains the normal way to stop an interactive
`cardboard-start` session. `cardboard-stop` stops only processes that belong
to this bench and leaves MariaDB and unrelated processes untouched. Both
commands are safe to run repeatedly. Migrations and asset builds remain
explicit commands and are intentionally not part of startup. Details:
`scripts/dev/README.md`.

## Operational workspace and dashboard

The public Cardboard Management Desk workspace keeps daily actions, ten operational
Number Cards, four Dashboard Charts, operational lists, inventory links, and
standard reports on one page. It ships as app-owned standard metadata under
`cardboard_management/cardboard_management/`.

Configure the dashboard through the single `Cardboard Dashboard Settings` document:

- `Company` deterministically scopes every metric.
- `Cardboard Item Group` scopes current stock and the item chart to that Item Group
  and its nested descendants.

No company or item name is hard-coded. Supply metrics query submitted Cardboard
Supply rows in warehouses belonging to the configured company. Expense metrics
query submitted Quick Expenses. Supplier-payment metrics aggregate standard
Payment Entry allocations against Purchase Invoices linked to Cardboard Supply.
Current stock comes from ERPNext Bin state, and supplier outstanding comes from
standard Payment Ledger Entry state. The app creates no summary table, scheduled
KPI table, stock balance, supplier balance, or custom ledger.

Quick Expense remains a thin operational document over standard Journal Entry
accounting. Scale Integration is still shown only as a future placeholder.

## Tests

Read-only foundation checks run without a database and do not create ERP records:

```bash
env/bin/python -m unittest discover \
  -s apps/cardboard_management/cardboard_management/tests -v
```

On a dedicated test site with tests enabled, the same suite can also be run through
Frappe without ERPNext test setup or test fixtures:

```bash
bench --site <test-site> run-tests --app cardboard_management \
  --skip-test-records --skip-before-tests
```

Tests cover the app foundation, weight calculations, validation, Purchase Invoice
mapping and idempotency, physical stock quantity, supplier liability, migration
schema, Payment Entry draft mapping, full/partial/deferred payments, over-allocation
protection, derived payment state, Quick Expense accounting, all dashboard metrics,
company and Item Group isolation, chart aggregation, widget metadata, workspace
layout, and cancellation reversal. Frappe tests use transactions and roll back
temporary records. Run them only on a local development or dedicated test site
with `allow_tests` enabled.

## Layout

- `cardboard_management/hooks.py`: app metadata, ERPNext dependency, and migration hooks.
- `cardboard_management/setup.py`: idempotent standard-DocType schema extensions.
- `cardboard_management/modules.txt`: Cardboard Management module declaration.
- `cardboard_management/cardboard_management/`: business DocTypes, controllers, and the
  public Cardboard Management workspace (`workspace/`, rendered by `workspace/content_builder.py`).
- `cardboard_management/tests/`: foundation and workspace source tests.
- `cardboard_management/patches.txt` and `patches/`: standard migration structure.
- `cardboard_management/public/`, `templates/`, `config/`: standard scaffold.
- `pyproject.toml`: Python packaging and generated development-tool settings.

## License

MIT. See [license.txt](license.txt).
