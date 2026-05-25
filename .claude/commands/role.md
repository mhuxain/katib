---
description: Adopt a specific SDLC role and execute one step. Intended for Claude sessions running inside a herdr pane spawned by the orchestrator. Do not use this command in the orchestrator's own session.
argument-hint: <role-name> <task-id> <step-kind> [--inputs-from <step-ids...>]
---

You are being commissioned for a single SDLC step. Parse `$ARGUMENTS` as positional args followed by optional `--inputs-from` step ids:

`<role-name> <task-id> <step-kind> [--inputs-from step-001 step-002 ...]`

Now execute, in order:

1. **Read your role definition**: `.claude/agents/<role-name>.md`. This defines what you do, what you do not do, and the shape of your output. Internalize it.
2. **Read the workflow contract**: `.claude/sdlc/README.md`. Re-read it on every dispatch — it is the contract you must follow.
3. **Read the task state**: `.claude/sdlc/task.py get --task-id <task-id>`. Confirm `assigned_agent` is your `<role-name>`. If not, stop and print an error to stdout — do not proceed.
4. **Read your inputs**: for each step id in `--inputs-from`, open the corresponding `output_path` from the state's `steps[]` and read it fully. Pay attention to the YAML frontmatter — that's the routing signal you should react to.
5. **Start the step**:
   ```
   STEP_ID=$(.claude/sdlc/task.py step-start \
     --task-id <task-id> \
     --agent <role-name> \
     --kind <step-kind> \
     --inputs-from <ids...>)
   ```
6. **Do your role's work.** Strictly per the role file. Do not route. Do not fix issues outside your scope. Do not impersonate other agents. If you need clarification, write it into your output and exit — the orchestrator will surface it to the user.
7. **Write your output** to `.claude/sdlc/tasks/<task-id>/$STEP_ID-<role-name>.md`. The file MUST start with a YAML frontmatter block containing at minimum:
   ```yaml
   ---
   agent: <role-name>
   task_id: <task-id>
   step_id: <step-id>
   status: pass | partial | fail
   ---
   ```
   Add role-specific keys per your role file: `blockers`, `recommendations`, `severity_summary`, `branch`, etc.
8. **Complete the step**:
   ```
   .claude/sdlc/task.py step-complete \
     --task-id <task-id> \
     --agent <role-name> \
     --status <pass|partial|fail> \
     --output .claude/sdlc/tasks/<task-id>/$STEP_ID-<role-name>.md \
     --findings '<json-array>'
   ```
   This releases the mutex so the orchestrator can dispatch the next agent.
9. **Print one summary line** to stdout in this exact shape, then idle:
   ```
   <step-id> complete: <status>; <one-line summary>
   ```

## If you cannot complete the step

Call `step-fail` with a concise reason, then idle:
```
.claude/sdlc/task.py step-fail --task-id <task-id> --agent <role-name> --reason "<reason>"
```
Print `<step-id> failed: <reason>` and stop. The orchestrator will decide what to do.

## Hard rules

- **Stay in role.** You are only the role named in `<role-name>` for this session.
- **No routing.** Do not say "now hand off to X." The orchestrator routes.
- **No scope creep.** Do not fix bugs, refactor, or add features that are not part of your commissioned step.
- **No direct state-file edits.** The python tool is the only way to update `task-<id>-state.json`.
- **No pushing, no PRs.** The implementer commits to `-wip` only; everything else is the user's call.
