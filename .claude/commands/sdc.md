---
description: Alias for /sdlc. Kicks off the full SDLC sub-agent cycle (analyst → plan → build → UAT → security) for a change request, feature, or bugfix.
argument-hint: <description of the change request, feature, or bugfix>
---

A new change request has been received:

> $ARGUMENTS

Run the SDLC sub-agent cycle defined in `.claude/agents/README.md`. Orchestrate each step yourself; do not let agents chain directly.

1. **Invoke `change-request-analyst`** with the request above. Present its "my understanding" checklist, open questions, and out-of-scope list to me. Wait for me to confirm or correct before proceeding.
2. Once confirmed, **invoke `planner`**. Present the plan and wait for my approval.
3. Once approved, **invoke `implementer`**. It will code the change, self-verify, and commit to a `-wip` branch. Do not push.
4. When the implementer reports done, **invoke `uat-tester`** with the `-wip` branch name plus the confirmed change request and approved plan.
5. After UAT passes (or with explicit go-ahead on PASS-WITH-NOTES), **invoke `security-tester`**.
6. End with a short summary: `-wip` branch name, UAT result, security findings by severity, and the recommended next step (e.g. open PR, fix blockers, request user review).

Rules:
- Do not skip steps.
- Do not invoke a later step until the prior step is approved or passes.
- If a step fails or surfaces blockers, return to the appropriate earlier step (usually the implementer on the same `-wip` branch) rather than continuing.
- Never push or open a PR without my explicit instruction.
