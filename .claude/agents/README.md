# SDLC role agents

Role definitions for the multi-agent SDLC workflow. Each file defines one role's identity, behavior, and output shape. The workflow that ties them together — state file, mutex, routing — lives in **[`.claude/sdlc/README.md`](../sdlc/README.md)**.

| File | Role | Model | Writes? |
|---|---|---|---|
| [`change-request-analyst.md`](./change-request-analyst.md) | Confirms user intent with a 10–20 bullet "my understanding" checklist | opus | No |
| [`planner.md`](./planner.md) | Codebase analysis + ordered implementation plan | opus | No |
| [`implementer.md`](./implementer.md) | Writes the code, self-verifies, commits to `<name>-wip` (no push) | sonnet | **Yes** |
| [`uat-tester.md`](./uat-tester.md) | Connects to user's Chrome via CDP, walks every acceptance criterion | sonnet | No |
| [`security-tester.md`](./security-tester.md) | OWASP-aligned static + dynamic security review | opus | No |
| [`orchestrator.md`](./orchestrator.md) | Owns all routing. The user's main Claude session adopts this role on `/sdlc`. | opus | No |

## How they're used

Roles are dispatched as **sibling Claude instances in herdr panes**, not as in-process sub-agents. The orchestrator (the user's main session) spawns a pane per role, sends `/role <name> <task-id> <kind>` to that pane, and waits for the role to:

1. Read its own role file (one of the files in this directory)
2. Read [`.claude/sdlc/README.md`](../sdlc/README.md) for the workflow contract
3. Call `.claude/sdlc/task.py step-start`
4. Do its role's work
5. Write its output markdown (with YAML frontmatter) under `.claude/sdlc/tasks/<task-id>/`
6. Call `.claude/sdlc/task.py step-complete`

Roles do not route. Roles do not hand off. Roles do not fix issues outside their scope. They only report outcomes. The orchestrator routes based on each output's YAML frontmatter.

## Adding a role

1. Add a new file here following the same shape: frontmatter (`name`, `description`, `model`, `tools`) + role body describing what the agent does, doesn't do, and produces.
2. Add the role to the table above.
3. If routing semantics change, update the routing rules in [`.claude/sdlc/README.md`](../sdlc/README.md).
4. If the orchestrator needs new judgment heuristics, update [`orchestrator.md`](./orchestrator.md).
