# SDLC sub agents — drafts

A set of Claude Code sub agents that cover the development lifecycle from understanding the user's request through security review of the finished change. **These are drafts** — feedback welcome before they're adopted.

## The flow

```
  user request
       │
       ▼
┌──────────────────────────┐
│ 1. change-request-analyst│   confirms understanding (10–20 bullet checklist)
└──────────────────────────┘
       │  user confirms / corrects
       ▼
┌──────────────────────────┐
│ 2. planner               │   read-only; produces an implementation plan
└──────────────────────────┘
       │  user approves
       ▼
┌──────────────────────────┐
│ 3. implementer           │   writes code, self-verifies, commits to `<name>-wip`
└──────────────────────────┘
       │  hands off branch
       ▼
┌──────────────────────────┐
│ 4. uat-tester            │   drives user's Chrome (CDP), checks vs. request + plan
└──────────────────────────┘
       │  pass
       ▼
┌──────────────────────────┐
│ 5. security-tester       │   OWASP-aligned review (static + dynamic)
└──────────────────────────┘
       │
       ▼
  branch ready for human review / PR
```

Orchestration is done by the main Claude — it picks the right agent based on where the work is in the flow. Sub agents do not invoke each other directly; they finish their job and recommend the next handoff.

## The agents

| # | Agent | Phase | Model | Writes? | Returns |
|---|---|---|---|---|---|
| 1 | `change-request-analyst` | Pre-plan | opus | No | 10–20 bullet "my understanding" + open questions + out-of-scope |
| 2 | `planner` | Plan | opus | No | Goal, approach, critical files, ordered change plan, test strategy, risks |
| 3 | `implementer` | Build | sonnet | **Yes** (code + commits to `-wip` branch; no push) | Branch name, files changed, verification output |
| 4 | `uat-tester` | Acceptance | sonnet | No | Pass/fail per acceptance criterion, edge-case findings, gaps vs. plan |
| 5 | `security-tester` | Security | opus | No | OWASP-aligned findings with severity, evidence, fix recommendations |

Only the implementer writes to the codebase. The implementer also commits — but only to a branch suffixed with `-wip`, and **never pushes**. Pushing and PR creation stay with the human (or with main Claude on explicit user instruction).

## Why each agent exists

- **change-request-analyst** — the cheapest bug to fix is one you catch before any planning starts. This agent forces an explicit "did we understand you?" gate, modeled on how a good senior engineer mirrors back a request before estimating it.
- **planner** — separates *what* from *how*. Produces an artifact the user (and the implementer agent) can both review. Mirrors Claude Code's plan mode.
- **implementer** — does the work, but also self-verifies. A human dev runs their code before sending to QA; this agent does too (Playwright MCP for UI, curl for APIs). The `-wip` branch convention keeps integration safe.
- **uat-tester** — the implementer's self-check is a smoke test. UAT walks every acceptance criterion against the real running app, in the user's real Chrome, and compares against both the request and the plan. Catches "built the wrong thing."
- **security-tester** — OWASP-aligned, two-pass (static read of the diff + dynamic probes). Run after UAT, or in parallel for security-sensitive changes.

## When to invoke each (triggers for main Claude)

- New feature, bug fix, or refactor request from the user → start with **change-request-analyst**.
- User says "go ahead" / "plan it" after analyst checklist confirmed → **planner**.
- Already-scoped task with clear AC → can go straight to **planner**.
- User approves a plan → **implementer**.
- Implementer reports done on a `-wip` branch → **uat-tester**.
- UAT passes, or the change touches auth / payments / user data / file upload / third-party calls → **security-tester**.
- UAT or security finds blockers → back to **implementer** on the same `-wip` branch.

## Requirements

- **Playwright MCP server** must be available for the implementer's UI smoke test, the uat-tester, and the security-tester's dynamic probes. If the MCP server isn't wired up, the implementer falls back to API curl checks; uat-tester and security-tester will say so explicitly rather than fake results.
- **Chrome with CDP** for uat-tester: launch with `--remote-debugging-port=9222` (or set the port the Playwright MCP server expects). The uat-tester connects to your existing browser; it does not launch a fresh one. This means it will see your real profile and logged-in sessions — useful, but be aware.
- **A running app** (local dev or staging) for any of the verifying agents to actually verify against.

## Model selection rationale

- `opus` for agents that need nuance — understanding fuzzy intent (analyst), making design tradeoffs (planner), and reasoning about security (security-tester).
- `sonnet` for agents that execute structured work — writing code to a spec (implementer), driving a browser through a checklist (uat-tester).

Adjust to taste. The model field is set per agent in the frontmatter.

## Extending

To add an agent (e.g. `release-notes-writer`, `migration-reviewer`, `perf-tester`):

1. Add a markdown file in this directory with YAML frontmatter (`name`, `description`, `model`, `tools`).
2. Make the `description` action-oriented and trigger-rich — that's what the main Claude uses to decide when to invoke.
3. Be explicit in the system prompt about what the agent **does not** do, especially around writes/commits/pushes.
4. Update the flow diagram and table above.

## Status

Drafts. Not yet adopted. Open questions before adoption:

- Should there be a sixth agent that handles release notes + PR description, triggered after security-tester passes?
- Should the implementer's "self-verification" step be split into its own agent for clearer separation of concerns?
- For purely backend changes with no UI, is the uat-tester still the right name, or should it split into `api-uat-tester` and `ui-uat-tester`?
