# MVP Operations Runbook

**Package:** P05-W01 — MVP Operational Readiness & End-to-End Validation  
**Environment:** WSL Ubuntu-24.04, bench `~/frappe/cardboard-bench`, site `cardboard.localhost`

This is the minimum local/pilot operating procedure. It does not replace the UAT checklist or backup procedure.

## Startup

From any WSL shell after installing the launcher:

```bash
cardboard-start
```

The launcher validates the bench/site, reuses an already-running environment, starts only the required local services when necessary, and runs Bench in the foreground. The normal stop action is `Ctrl+C` when the foreground process is owned by the operator.

Do not run a second Bench instance on the same ports. The launcher is intended to refuse unrelated port holders rather than terminate them.

## Stop

```bash
cardboard-stop
```

This stops only processes identified as belonging to the Cardboard bench and cleans its bench Redis processes. It leaves MariaDB running and does not touch unrelated processes.

## Status and health

```bash
cd ~/frappe/cardboard-bench
bench doctor
curl -fsS -o /tmp/cardboard-ping \
  -w 'HTTP %{http_code}\n' \
  http://cardboard.localhost:8000/api/method/frappe.ping
```

Expected health response:

```json
{"message":"pong"}
```

For the current development site, `bench doctor` reported one worker online. The scheduler was disabled/inactive; confirm this is intentional before a pilot that depends on scheduled jobs.

## Common recovery commands

Use these only after checking whether the environment is already running:

```bash
cd ~/frappe/cardboard-bench
bench --site cardboard.localhost list-apps
bench --site cardboard.localhost migrate
bench build --app cardboard_management
```

Migration and build are explicit maintenance operations; they are not part of the startup launcher. Never recreate the site or reset the database as a recovery step.

If a port is held by an unrelated process, identify and resolve it with the environment owner. Do not kill it blindly. If a required service is down, capture the exact error and use the smallest approved environment repair; do not start duplicate MariaDB/Redis/Bench instances.

## Where to inspect failures

### Bench and process logs

From the bench root:

```bash
cd ~/frappe/cardboard-bench
ls logs
```

Inspect the relevant file without exposing credentials:

- `logs/web.error.log` — web request and application errors.
- `logs/worker.error.log` — background worker failures.
- `logs/schedule.log` — scheduler activity/errors when the scheduler is enabled.
- `logs/bench.log` — Bench process output where present.
- `logs/node-socketio.error.log` — Socket.IO/node errors where present.

The exact set of files can vary by Bench version and process configuration.

### Frappe application errors

Use the site’s **Error Log** surface or the administrator-supported Frappe error-log query. Filter by the time of the failed action and the affected operational document. Preserve the error code/message and document ID, not secrets or raw credentials.

### Frontend errors

For a browser-side failure, capture:

- route URL;
- signed-in role (not password/token);
- visible Arabic error/state;
- browser console error and failed RPC method, if present;
- affected operational document ID and date range.

Do not treat a permanent spinner as success. Refresh once only after recording the state, then report whether the backend document was created/submitted before retrying.

### Failed business actions

For Supply, Sale, Supplier Payment, and Quick Expense, first read the custom document status and linked native document status. Do not repair balances by editing Payment Entry, Journal Entry, Purchase Invoice, Stock Entry, or ledger rows directly. Use the operational lifecycle or escalate with the exact IDs and error message.

## Diagnostic capture template

```text
Date/time:
Site:
Route/API method:
User role:
Operational document ID:
Linked native document ID (if any):
Expected action:
Visible Arabic message:
HTTP/RPC result:
Relevant log file and timestamp:
Was any retry made:
Result:
```

## Current readiness note

The current site passed `frappe.ping` with HTTP 200 and `{"message":"pong"}`. Startup procedure and diagnostics are documented; complete authenticated UAT and the disposable-copy backup/recovery rehearsal before relying on the environment for real pilot data.