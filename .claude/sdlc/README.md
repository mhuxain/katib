# SDLC workflow — spec

How a change request moves from "user typed `/sdlc`" to "verified `-wip` branch ready for human PR review."

This document is the contract every agent must follow. The orchestrator agent and the five role agents read it on every invocation. The Python state-tool enforces it.

## The model

- **One task** = one change request (a feature, bugfix, or refactor).
- **One state file** = `.claude/sdlc/tasks/<task-id>-state.json` is the source of truth for that task.
- **N steps** per task = one entry per agent invocation, appended to `state.steps[]` in order.
- **One assigned agent at a time.** The state file's `assigned_agent` field is a mutex.

## State file schema

```json
{
  "task_id": "task-01",
  "description": "Add invoice CRUD per FR-12",
  "created_at": "2026-05-25T10:00:00Z",
  "updated_at": "2026-05-25T10:30:00Z",
  "assigned_agent": null,
  "current_step_id": null,
  "steps": [
    {
      "id": "step-001",
      "agent": "analyst",
      "kind": "confirm-intent",
      "status": "complete",
      "started_at": "2026-05-25T10:00:00Z",
      "finished_at": "2026-05-25T10:05:00Z",
      "output_path": ".claude/sdlc/tasks/task-01/step-001-analyst.md",
      "result": "pass",
      "findings": [],
      "inputs_from": []
    }
  ],
  "releases": []
}
```

Field notes:

- `assigned_agent` — `null` or the name of the agent that currently holds the mutex.
- `current_step_id` — `null` or the id of the in-progress step (always owned by `assigned_agent`).
- `steps[]` — append-only log. Status values: `in_progress` | `complete` | `failed`. Result values (set on completion): `pass` | `partial` | `fail`.
- `inputs_from` — list of prior step ids this step depended on (so the orchestrator can reconstruct dependencies).
- `findings` — opaque JSON array; the tool stores but does not validate. See "Findings schema" below.
- `releases[]` — audit log of forced mutex releases (crash recovery).

## Findings schema (convention, not enforced)

For uat-tester and security-tester especially, the orchestrator needs to route based on findings. Use this shape:

```json
{
  "id": "F-001",
  "severity": "critical | high | medium | low | info",
  "title": "Short summary",
  "category": "owasp-A03 | uat-gap | regression | ...",
  "location": "path:line or endpoint",
  "evidence": "...",
  "fix_recommendation": "...",
  "complexity": "simple | complex"
}
```

`complexity` is the hint the orchestrator uses to decide implementer (simple) vs. planner re-plan (complex).

## Agent output markdown

Every step writes its output to `.claude/sdlc/tasks/<task-id>/<step-id>-<agent>.md`. The file MUST begin with a YAML frontmatter header so the orchestrator can route deterministically without re-reading prose:

```markdown
---
agent: security-tester
task_id: task-01
step_id: step-005
status: partial
severity_summary:
  critical: 0
  high: 1
  medium: 2
  low: 3
blockers:
  - "F-001: SQL injection in /api/invoices/search"
recommendations:
  - "Implementer fix F-001 (simple)"
  - "Planner re-plan input validation strategy (complex, blocks F-003 + F-004)"
---

# Security review: task-01 step-005

[full markdown content follows]
```

Required keys: `agent`, `task_id`, `step_id`, `status`. Other keys are role-specific.

## Python tool CLI

Invoke as `.claude/sdlc/task.py <verb> [args...]`. Stdlib only; no install needed.

| Verb | Purpose |
|---|---|
| `init --task-id <id> --description <text>` | Create a new task state file. Fails if task already exists. |
| `get --task-id <id>` | Print state file as JSON to stdout. |
| `status --task-id <id>` | Print human-readable summary (assigned agent, current step, counts). |
| `assign --task-id <id> --agent <name>` | Acquire the mutex. Fails if already held by another agent. |
| `release --task-id <id> [--force --reason <text>]` | Release the mutex. `--force` for crash recovery; reason is logged. |
| `step-start --task-id <id> --agent <name> --kind <kind> [--inputs-from <ids...>]` | Append a new in_progress step. Fails if caller isn't the assigned agent or another step is in progress. Prints the new step id. |
| `step-complete --task-id <id> --agent <name> --status <pass\|partial\|fail> --output <md-path> [--findings <json>]` | Finalize the current step, release the mutex. |
| `step-fail --task-id <id> --agent <name> --reason <text>` | Mark the current step failed, release the mutex. Use when the agent cannot produce a usable output. |

Exit codes: `0` ok, `1` argument/usage error, `2` not-found, `3` mutex / state violation.

## Agent contract

Every SDLC role agent, when invoked via `/role <name> <task-id> <kind>` inside its pane, MUST:

1. Read its own role file at `.claude/agents/<name>.md`.
2. Read this README to refresh the workflow contract.
3. Read `.claude/sdlc/tasks/<task-id>-state.json` to learn its assigned step's `inputs_from`.
4. Read every input markdown listed in `inputs_from`.
5. Call `.claude/sdlc/task.py step-start ...` BEFORE doing any work. (The orchestrator will already have called `assign` for you.)
6. Do its role work exactly as the role file describes. Do **not** route. Do **not** fix issues outside the role's scope. Do **not** hand off.
7. Write its output markdown to `.claude/sdlc/tasks/<task-id>/<step-id>-<agent>.md` with the required YAML frontmatter.
8. Call `.claude/sdlc/task.py step-complete ...` with the output path and findings JSON. This releases the mutex.
9. Print a one-line summary to its pane's stdout (so the orchestrator's `pane read` sees a clear signal) and idle.

If the agent encounters an unresolvable error before producing output, call `step-fail` with a reason and idle.

## Orchestrator contract

The orchestrator is the user's main Claude session, configured by `.claude/agents/orchestrator.md`. On `/sdlc <change request>` it:

1. Picks the next `task-NN` id, runs `task.py init`.
2. Loops:
   - Reads state via `task.py get`.
   - Decides the next role and step kind based on state, findings, and routing rules in its agent file.
   - Surfaces relevant info to the user, gets confirmation at gates (after analyst, after planner).
   - Spawns (or reuses) a herdr pane for the role: `herdr tab create --label <role>`, then `herdr pane run` to start Claude with the right model.
   - Waits for that pane's Claude to be idle: `herdr pane wait <id> --state idle`.
   - Acquires the mutex: `task.py assign --agent <role>`.
   - Dispatches: `herdr pane run <id> "/role <role> <task-id> <kind>"`.
   - Waits for the step to complete (polls `task.py status` or watches for the agent's stdout summary line).
   - Reads the step's output markdown frontmatter to decide next routing.
3. Exits the loop when security passes (or with user override on `partial`).
4. Never writes code itself. Never edits the state file directly.

## Routing rules (orchestrator defaults)

- Analyst output `status: pass` and user confirms → planner.
- Analyst output `status: partial` (open questions) → surface to user, re-invoke analyst with answers.
- Planner output user-approved → implementer.
- Implementer output `status: pass` → uat-tester. `status: fail` → back to implementer (or planner if implementer flags plan as wrong).
- UAT `status: pass` → security-tester. `partial` or `fail` with `complexity: simple` findings → implementer. With `complexity: complex` findings → planner re-plan.
- Security `status: pass` → done; surface `-wip` branch to user. `partial`/`fail` → route per `complexity` like UAT.

## Example: cycle walkthrough

User: `/sdlc add invoice CRUD per FR-12, see docs/fr-12.md`

```
orchestrator: task.py init --task-id task-01 --description "Add invoice CRUD per FR-12"
orchestrator: herdr tab create --label analyst -> pane 1-2
orchestrator: herdr pane run 1-2 "claude --model opus"
orchestrator: herdr pane wait 1-2 --state idle
orchestrator: task.py assign --task-id task-01 --agent analyst
orchestrator: herdr pane run 1-2 "/role analyst task-01 confirm-intent"

analyst (in pane): reads files, produces .claude/sdlc/tasks/task-01/step-001-analyst.md
analyst (in pane): task.py step-complete --status pass --output ... --findings []
analyst (in pane): prints "step-001 complete: pass; checklist 14 items; 2 open questions"

orchestrator: reads frontmatter, surfaces checklist + open questions to user
user: confirms with answers
orchestrator: task.py assign --agent analyst; herdr pane run 1-2 "/role analyst task-01 refine-intent --inputs-from step-001"
... (and so on through planner → implementer → uat → security)
```

## Status

Drafts. Schema, tool, and agent contracts will be refined when the first real cycle exercises them. Breaking changes are fine until v1.
