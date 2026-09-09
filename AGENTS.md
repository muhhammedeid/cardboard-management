# Cardboard Management — Agent Operating System

Lead/delegation workflow for all agent work in this repository.
Canonical principles: **Think expensive. Execute cheap. Verify efficiently. Approve carefully.**

## 1. Project context

- Custom Frappe v15 app for a cardboard recycling/trading ERP.
- Bench: `~/frappe/cardboard-bench` inside WSL distro `Ubuntu-24.04` (user `twenty`).
  Site: `cardboard.localhost` — http://cardboard.localhost:8000
- From the Windows host, run WSL commands as
  `wsl.exe -d Ubuntu-24.04 -- bash -c "..."` (scripts: heredoc-via-stdin for anything complex;
  strip CRLF when moving files: `tr -d '\r'`).
- Dev environment start/stop: `cardboard-start` / `cardboard-stop` (see `scripts/dev/README.md`).
- Work-package history and decisions live in `docs/`.

### Architectural boundaries (never violate)

```text
ERPNext               = ERP / accounting / stock platform engine (read-only)
Frappe                = framework (read-only)
cardboard_management  = business-specific application and UX layer (writable)
```

Never modify `apps/frappe/` or `apps/erpnext/` for convenience. Default writable scope is
`apps/cardboard_management/`, but every Work Package must narrow ownership further.
Workers never treat the whole app as writable unless the task genuinely requires it.

## 2. Operating model

```text
User
 → Primary Hermes Agent (Lead: architect / planner / reviewer / final authority)
 → Delegated subagents (configured low-cost delegation lane)
 → Structured handoff
 → Lead review → APPROVED / REJECTED — REPAIR REQUIRED / BLOCKED — USER DECISION REQUIRED
```

The Lead owns: architecture, planning, decomposition, business-rule interpretation, risk,
security-sensitive and scope decisions, reviewing delegated work, and final acceptance.
The Lead is not the default implementation worker.

The Lead implements directly only when: the change is trivial; delegation overhead exceeds
implementation; continuous architectural judgment is required; a delegated repair repeatedly
failed; or safe isolation is impossible. Otherwise: **DELEGATE**.

Delegation lane (V1): the single configured Hermes delegation provider/model — read
`delegation.provider` / `delegation.model` from the Hermes config for the current lane.
Do not redesign Hermes for multi-model routing; single-lane delegation is acceptable.

**User override (highest authority):** the user may restrict a conversation to its assigned
model only. When the user says delegation/child sessions are not permitted for the current
conversation, do not delegate — keep the work in the Lead context. Delegation happens only
when the user has authorized it for that conversation or work package.

## 3. Work Package system

Subagents never receive vague implementation prompts. The Lead converts substantial work
into bounded Work Packages (this template; per-package history is kept in `docs/`):

```text
# PXX-WXX — TITLE
Mode: WRITE | READ
Risk: LOW | MEDIUM | HIGH

## Objective          — one precise deliverable
## Context            — minimum sufficient background (files, business rules, env facts)
## Dependencies       — packages/migrations that must exist first
## Writable Ownership — exact files/directories
## Read-Only          — areas that may be inspected but not changed
## Required Behavior  — numbered, specific
## Constraints        — no unrelated refactoring, no architecture changes,
                        no core ERPNext/Frappe modifications, no dependency changes
                        unless authorized, no destructive git/DB operations
## Explicitly Out of Scope
## Verification       — exact commands and expected evidence
## Acceptance Criteria — checkable list
## Required Handoff   — the structured contract (section 5)
```

## 4. Delegation policy

Delegate aggressively for bounded, implementation-oriented work: repository inspection,
targeted coding, tests, bug fixes, CSS/JS, translations, reports after specification,
documentation, fixtures, mechanical refactoring, repetitive changes, targeted verification.

Keep with the Lead: architecture, ambiguous requirements, business-rule decisions, security
boundaries, destructive data decisions, cross-module design, scope expansion, final review,
final approval.

Workers have implementation authority only. Workers must NOT: redefine requirements, change
architecture, expand scope, modify files outside ownership, weaken tests, suppress failures,
perform destructive DB operations, touch ERPNext/Frappe core, change dependencies without
approval, or start unrelated work. If any of these becomes necessary the worker returns
`BLOCKED — LEAD DECISION REQUIRED` instead of guessing.

### Context policy

Do not forward the whole parent conversation. Give each worker only: objective, relevant
architecture, relevant files, business rules, constraints, acceptance criteria, verification
commands. Ask for results, evidence, changed files, and risks — not internal diaries.

### Parallelism

Parallel delegation only with non-overlapping writable ownership, no ordering dependency,
and no shared migration/state assumptions. Never let two workers modify the same file.
Default maximum: 2–3 concurrent workers. Do not create concurrency merely because it exists.

## 5. Required worker handoff format

```text
STATUS: PASS | FAIL | BLOCKED | IMPLEMENTATION PASS — USER VISUAL QA REQUIRED
WORK PACKAGE: <ID>
FILES CHANGED:
- ...
IMPLEMENTED:
- ...
VERIFICATION:
- <command>
  <result>
ACCEPTANCE CRITERIA:
- [x] ...
- [ ] ...
NOT CHANGED:
- ...
RISKS / CAVEATS:
- none | ...
FOLLOW-UP:
- none | ...
```

Concise. No diary of every action. Never claim PASS without real verification evidence;
if testing is impossible, say so instead of fabricating evidence.

Visual QA is mandatory for final acceptance, but execution of visual QA is USER-OWNED.
Agents must stop and request the required user evidence. Do not report BLOCKED merely
because authenticated screenshots have not yet been supplied.

## 6. Lead review gate

A worker reporting PASS does not complete the Work Package. The Lead independently reviews:
scope compliance, `git diff`, changed files, architecture compliance, acceptance criteria,
test evidence, potential regressions, and security implications where applicable. The Lead
issues exactly one of:

```text
APPROVED
REJECTED — REPAIR REQUIRED
BLOCKED — USER DECISION REQUIRED
```

For localized defects prefer: review → targeted repair task → delegate repair → review again.
Do not silently repair every delegated defect.

Visual QA is mandatory for final acceptance, but execution of visual QA is USER-OWNED.
Agents must stop and request the required user evidence. The Lead may close a package as
APPROVED only after the user confirms the requested visual checks.

## Manual Visual QA & Fail-Fast Execution Policy

### Visual QA

Visual verification is USER-OWNED.

Agents must NOT:

- launch or control browsers for visual QA;
- attempt authenticated browser automation;
- spend tokens retrying browser drivers;
- infer visual correctness from screenshots they cannot access;
- repeatedly troubleshoot browser-profile/session issues.

If visual verification is required:

1. complete all source/runtime/automated verification possible;
2. stop at the visual gate;
3. tell the user exactly which screen(s) to open;
4. tell the user exactly what to visually verify;
5. request screenshots only when they are genuinely needed.

Return:

```text
VISUAL QA: PENDING USER VERIFICATION
```

This is NOT considered an implementation failure.

The user owns the final visual confirmation.

### Runtime / Build Fail-Fast Policy

If a required command fails, including:

- bench build
- bench migrate
- tests
- runtime startup
- Redis
- MariaDB
- Node/Corepack/Yarn
- asset compilation
- site access

the agent must NOT enter an open-ended troubleshooting loop.

Allowed behavior:

1. inspect the immediate error;
2. perform at most one narrow, low-risk diagnostic step when it directly identifies the cause;
3. if the next action requires:
   - environment changes;
   - service restart;
   - cache deletion;
   - package installation;
   - version switching;
   - destructive command;
   - broad workaround;
   - repeated retries;

STOP.

Return:

```text
BLOCKED — USER ACTION REQUIRED
```

Include:

- exact failed command;
- exact relevant error;
- likely cause, if known;
- whether code changes are involved;
- the smallest recommended next action for the user.

Do not keep trying alternate approaches merely to obtain PASS.

### No Silent Workarounds

Agents must not silently:

- switch Node versions;
- use alternate caches;
- restart the development environment;
- kill processes;
- modify global tooling;
- start services;
- change package-manager versions;
- bypass failing tests;
- skip verification gates;

unless the Work Package explicitly authorizes that exact action.

If authorization is not explicit:

ASK THE USER.

### User-Assisted Verification

If the agent needs information from a running UI to continue implementation, ask the user
for the minimum required evidence.

Examples:

- "Please open Cardboard Supplier Payment and send a screenshot of the amount field."
- "Please click الموردون and tell me which route opens."
- "Please run this command and send me the output."

Do not attempt expensive browser automation first.

### Completion Status

When implementation and automated verification pass but manual visual QA remains:

```text
STATUS:
IMPLEMENTATION PASS — USER VISUAL QA REQUIRED
```

Do not report BLOCKED unless actual implementation progress cannot continue.

After the user confirms the requested visual checks, the Lead may close the package as
APPROVED.

## 7. Escalation rules

A worker must escalate (never guess through) when: requirements conflict; architecture, scope,
or ownership must change; a destructive migration may be required; ERPNext/Frappe core appears
to require modification; a security assumption changes; tests expose an unrelated regression;
a product decision is required; or the worker is not confident the requested implementation
is safe.

## 8. Git and database safety

- Before any WRITE Work Package: inspect `git status`, distinguish pre-existing changes,
  preserve unrelated user changes.
- Never use `git reset --hard` or `git clean -fd` to simplify execution.
- Never automatically: reinstall the site, recreate databases, delete user data, reset
  migrations, run destructive SQL, remove sites. A development environment is not permission
  to destroy state.
- Test policy: run the smallest relevant test first (targeted Frappe/Python test, syntax
  check, lint, build verification), then broader verification when warranted.

## 9. Definition of done

```text
Requirement → Lead analysis → Work Package → Delegated implementation
→ Verification → Structured handoff → Lead review → Repair if required → APPROVED
```

Only the Lead closes a Work Package. Existing code is not sufficient.

Visual QA is mandatory for final acceptance, but execution of visual QA is USER-OWNED.
Agents must stop and request the required user evidence.

## 10. Verification quick reference

```bash
# inside WSL, bench dir:
bench --site cardboard.localhost list-apps
env/bin/python -m unittest discover -s apps/cardboard_management/cardboard_management/tests -v
# dev environment:
cardboard-start   # foreground bench start; Ctrl+C stops it
cardboard-stop
```

Read-only source tests (no DB) and the documented bench test suite are described in `README.md`.
