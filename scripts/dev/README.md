# Cardboard dev launchers

Two one-command launchers for the local Cardboard Management development
environment inside WSL (`~/frappe/cardboard-bench`, site `cardboard.localhost`):

```bash
cardboard-start   # prepare the environment, then run bench start (foreground)
cardboard-stop    # stop this bench and clean its Redis processes
```

## Install

From this directory (`apps/cardboard_management/scripts/dev/`):

```bash
bash install.sh
```

This symlinks both commands into `~/.local/bin`, which is already on `$PATH`
via `~/.profile`. No shell configuration is changed. Rerun `install.sh` after
pulling changes to the scripts.

## `cardboard-start`

1. Validates the bench directory, `Procfile`, and `sites/cardboard.localhost`.
2. Reconstructs the interactive environment itself (`~/.local/bin` for the
   `bench` uv tool, nvm for Node), so it works from any shell and directory.
3. Exits early with the site URL if the bench is already running.
4. Starts MariaDB **only if it is not already running**.
5. Cleans stale bench Redis processes on ports 13000/11000 — only processes
   that are verifiably `redis-server` with a working directory inside this
   bench; anything else aborts with an error instead of being killed.
6. Runs `bench start` in the foreground via `exec`, so live Bench logs appear
   in the terminal.

`Ctrl+C` remains the normal way to stop an interactive `cardboard-start`
session. `cardboard-start` is safe to run twice; the second run exits
successfully with "already running".

Environment override: set `CARDBOARD_BENCH_DIR` to point at a different bench
checkout (defaults to `~/frappe/cardboard-bench`).

## `cardboard-stop`

Stops only processes that belong to this bench: the `honcho` manager, `bench
serve/socketio/worker/schedule/watch` processes, Frappe node/esbuild helpers,
and bench Redis instances on ports 13000/11000. Everything is matched by
process name **and** working directory under the bench directory, so unrelated
processes are never signalled. MariaDB is left running.

Running `cardboard-stop` while nothing is running is safe and exits 0.

## Intentionally out of scope

Migrations and asset builds remain explicit manual commands and are **not**
part of startup:

```bash
bench --site cardboard.localhost migrate
bench build --app cardboard_management
```

The scripts never touch database contents, never create/delete sites, never
delete Redis data files, and never modify Frappe/ERPNext core.
