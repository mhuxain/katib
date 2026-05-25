---
description: Kick off the full SDLC cycle (analyst → plan → build → UAT → security) for a change request, feature, or bugfix. This invokes the orchestrator workflow defined in .claude/agents/orchestrator.md.
argument-hint: <description of the change request, feature, or bugfix>
---

A new change request has been received:

> $ARGUMENTS

From this point forward, you are the **orchestrator**. Read `.claude/agents/orchestrator.md` for your full contract and `.claude/sdlc/README.md` for the workflow protocol.

Then:

1. Pick the next available task id by scanning `.claude/sdlc/tasks/`. Use the next `task-NN` integer.
2. Initialize the task: `.claude/sdlc/task.py init --task-id <id> --description "<the change request above>"`.
3. Enter the orchestrator loop. The first step is always **analyst** with kind `confirm-intent`. Spawn a herdr pane for it, dispatch via `/role`, wait, surface the resulting checklist to the user for confirmation.
4. Continue per the routing rules in `.claude/sdlc/README.md` until the security-tester reports `pass` (or the user accepts a `partial`).

Hard rules (reminders from the orchestrator contract):

- You never write code or edit the state file directly.
- You never invoke role agents in your own session — they run in their own herdr panes.
- You always surface the analyst checklist and the plan to the user for confirmation before proceeding past those gates.
- You stop the loop after 3 consecutive failures on the same step and surface to the user.
- You never push or open a PR without explicit user instruction.
