# Coding guidance

Keep code simple. Do the requested change, nothing more.

- No premature abstractions. Three similar lines is fine — abstract on the third repeat, not the first.
- No speculative features, options, or config for hypothetical future needs.
- No error handling for cases that cannot happen. Validate at system boundaries only.
- No backwards-compatibility shims for code that has no other callers.
- Default to no comments. Add one only when the *why* is non-obvious.
- Prefer editing existing files over creating new ones.

# Project direction: multi-agent SDLC workflow

This repo is developing a multi-agent workflow that takes a change request through
**analyst → plan → build → UAT → security** with one specialized AI agent per phase
and a single orchestrator that owns all routing decisions.

## Goal

A user types `/sdlc <change request>` and a coordinated set of agents drives it to a
verified, security-reviewed `-wip` branch ready for human PR review — with explicit
gates for user confirmation at each phase.

## Architecture decisions

1. **Sibling Claude instances in herdr panes, not in-process sub-agents.** Each role
   runs as its own long-lived Claude session in a herdr pane. This enables pause/resume,
   direct user interaction with each role, parallel execution where useful, and per-role
   isolation (model, MCP servers, OS permissions).

2. **Shared JSON state file per task** at `.claude/sdlc/tasks/<task-id>-state.json` is
   the single source of truth. It tracks the assigned agent, the step log (append-only),
   pointers to each step's output markdown, and structured findings.

3. **Tool-mediated state writes only.** Agents never edit the state file directly. They
   call `.claude/sdlc/task.py` which enforces schema, the one-agent-at-a-time mutex, and
   the append-only step log. This keeps the state machine honest even when LLMs are sloppy.

4. **Pure-function agents.** Each SDLC agent reads inputs from state, produces its required
   output (a markdown file with a YAML frontmatter header the orchestrator can parse), and
   updates state via the tool. Agents do **not** route work, do **not** hand off, and do
   **not** fix issues outside their own scope. They only report outcomes.

5. **Orchestrator owns all routing.** The user's main Claude session, configured by
   `.claude/agents/orchestrator.md`, reads state, picks the next agent, spawns its pane,
   and assigns the task. When an agent surfaces findings, the orchestrator decides who
   addresses them (simple fix → implementer; complex one → planner re-plan).

6. **Mutex enforced by the tool.** Exactly one agent is assigned to a task at any moment.
   The tool rejects `step-start`, `step-complete`, and `step-fail` calls from any agent
   other than the assigned one. Crashes can be cleared with `release --force --reason`.

## Where things live

| Path | Purpose |
|---|---|
| `.claude/agents/*.md` | Role definitions: analyst, planner, implementer, uat-tester, security-tester, orchestrator |
| `.claude/sdlc/README.md` | Full workflow spec, state schema, tool CLI reference, examples |
| `.claude/sdlc/task.py` | Python state-tool. Stdlib only. Atomic writes. Mutex. |
| `.claude/sdlc/tasks/` | Per-task state files and the markdown outputs each step produces |
| `.claude/commands/sdlc.md` | `/sdlc <change request>` — the user-facing entry point |
| `.claude/commands/role.md` | `/role <role-name> <task-id> <step-kind>` — used inside a spawned pane |

## Status

Drafts. The agent definitions, the state schema, and the python tool will be refined
as the first end-to-end cycle is exercised on a real change.
