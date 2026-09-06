# Cardboard Management

A custom Frappe v15 app for a small local cardboard recycling and trading ERP.

## Architecture and scope

- **ERPNext remains the ERP engine.**
- **Frappe remains the framework.**
- **cardboard_management contains only business-specific customization and code.**

All custom code belongs in `apps/cardboard_management`. Do not modify
`apps/frappe` or `apps/erpnext`.

P00-W01 establishes the app package and the **Cardboard Management** module only.
It adds no Cardboard Supply DocType, accounting or stock logic, dashboards,
workflows, business records, or business rules.

## Requirements

- Frappe v15 and ERPNext v15, installed and managed by Bench.
- This foundation was created on Frappe 15.120.0 and ERPNext 15.121.0.
- ERPNext is declared in `required_apps`; this app does not replace ERPNext.

## Current business model

### Cardboard Supply

`Cardboard Supply` records one cardboard Item per transaction, measured in Kg,
against a standard ERPNext Supplier and Warehouse. The server calculates net
weight and total amount and validates the weight and rate boundaries. The
DocType is submittable and uses `CS-.YYYY.-.#####` naming.

Submitting a Cardboard Supply currently creates no Purchase Invoice, Purchase
Receipt, stock ledger entry, GL entry, payment, workflow, or dashboard. ERPNext
remains authoritative for those domains when later phases explicitly integrate
them.

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
There are no custom install/migration hooks, fixtures, schema changes, or data
patches. `patches.txt` retains the standard empty migration sections. Future
schema changes and idempotent patches must stay within this app and be verified
with repeated migrations. Do not use core edits or manual database changes as
an installation requirement.

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

Tests cover the ERPNext dependency, module declaration/import, and absence of
business event and migration hooks. Place future tests in the app package; use
Frappe's test conventions for future DocTypes. Do not run record-creating tests
against a business-data site.

## Layout

- `cardboard_management/hooks.py`: app metadata and ERPNext dependency.
- `cardboard_management/modules.txt`: Cardboard Management module declaration.
- `cardboard_management/cardboard_management/`: business module package, empty for now.
- `cardboard_management/tests/`: foundation tests.
- `cardboard_management/patches.txt` and `patches/`: standard migration structure.
- `cardboard_management/public/`, `templates/`, `config/`: standard scaffold.
- `pyproject.toml`: Python packaging and generated development-tool settings.

## License

MIT. See [license.txt](license.txt).
