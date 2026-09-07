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
STATUS: PASS | FAIL | BLOCKED
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
