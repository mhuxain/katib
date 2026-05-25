#!/usr/bin/env python3
"""SDLC task state tool.

Mediates writes to .claude/sdlc/tasks/<task-id>-state.json. SDLC agents must
call this tool rather than editing the state file directly. The tool enforces
the schema, the one-agent-at-a-time mutex, and the append-only step log.

See .claude/sdlc/README.md for the full workflow contract and CLI reference.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

TASKS_DIR = Path(".claude/sdlc/tasks")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def task_path(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}-state.json"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        die(f"task state not found: {path}", 2)
    return json.loads(path.read_text())


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    os.replace(tmp, path)


def die(msg: str, code: int = 1) -> None:
    print(f"task.py: {msg}", file=sys.stderr)
    sys.exit(code)


def require_assigned(state: dict[str, Any], agent: str) -> None:
    if state["assigned_agent"] != agent:
        die(
            f"agent '{agent}' is not the assigned agent "
            f"(assigned: {state['assigned_agent']})",
            3,
        )


def find_current_step(state: dict[str, Any]) -> dict[str, Any]:
    sid = state["current_step_id"]
    if sid is None:
        die("no step is currently in progress", 3)
    for s in state["steps"]:
        if s["id"] == sid:
            return s
    die(f"current_step_id {sid} not found in steps[] (state corruption)", 3)


def cmd_init(args: argparse.Namespace) -> None:
    path = task_path(args.task_id)
    if path.exists():
        die(f"task already exists: {path}", 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    (TASKS_DIR / args.task_id).mkdir(parents=True, exist_ok=True)
    state = {
        "task_id": args.task_id,
        "description": args.description,
        "created_at": now(),
        "updated_at": now(),
        "assigned_agent": None,
        "current_step_id": None,
        "steps": [],
        "releases": [],
    }
    save_state(path, state)
    print(path)


def cmd_get(args: argparse.Namespace) -> None:
    sys.stdout.write(task_path(args.task_id).read_text())


def cmd_status(args: argparse.Namespace) -> None:
    state = load_state(task_path(args.task_id))
    print(f"Task:        {state['task_id']}")
    print(f"Description: {state['description']}")
    print(f"Assigned:    {state['assigned_agent'] or '(none)'}")
    print(f"Current:     {state['current_step_id'] or '(none)'}")
    counts = {"complete": 0, "failed": 0, "in_progress": 0}
    for s in state["steps"]:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    print(
        f"Steps:       {counts['complete']} complete, "
        f"{counts['failed']} failed, {counts['in_progress']} in progress"
    )
    if state["steps"]:
        last = state["steps"][-1]
        print(
            f"Last step:   {last['id']} "
            f"agent={last['agent']} kind={last['kind']} "
            f"status={last['status']} result={last.get('result') or '-'}"
        )


def cmd_assign(args: argparse.Namespace) -> None:
    path = task_path(args.task_id)
    state = load_state(path)
    held = state["assigned_agent"]
    if held and held != args.agent:
        die(
            f"task already assigned to '{held}'; "
            f"release first or use --force-takeover",
            3,
        )
    state["assigned_agent"] = args.agent
    save_state(path, state)


def cmd_release(args: argparse.Namespace) -> None:
    path = task_path(args.task_id)
    state = load_state(path)
    held = state["assigned_agent"]
    if held is None and not args.force:
        die("task is not assigned", 3)
    if state["current_step_id"] is not None and not args.force:
        die(
            f"step {state['current_step_id']} is still in_progress; "
            f"use step-complete or step-fail, or --force",
            3,
        )
    state["releases"].append(
        {
            "at": now(),
            "agent": held,
            "step_id": state["current_step_id"],
            "reason": args.reason or "(none)",
            "forced": bool(args.force),
        }
    )
    state["assigned_agent"] = None
    if args.force:
        state["current_step_id"] = None
    save_state(path, state)


def cmd_step_start(args: argparse.Namespace) -> None:
    path = task_path(args.task_id)
    state = load_state(path)
    require_assigned(state, args.agent)
    if state["current_step_id"] is not None:
        die(f"another step is already in progress: {state['current_step_id']}", 3)
    step_id = f"step-{len(state['steps']) + 1:03d}"
    state["steps"].append(
        {
            "id": step_id,
            "agent": args.agent,
            "kind": args.kind,
            "status": "in_progress",
            "started_at": now(),
            "finished_at": None,
            "output_path": None,
            "result": None,
            "findings": [],
            "inputs_from": args.inputs_from or [],
        }
    )
    state["current_step_id"] = step_id
    save_state(path, state)
    print(step_id)


def cmd_step_complete(args: argparse.Namespace) -> None:
    path = task_path(args.task_id)
    state = load_state(path)
    require_assigned(state, args.agent)
    step = find_current_step(state)
    if step["agent"] != args.agent:
        die(f"step {step['id']} is owned by {step['agent']}, not {args.agent}", 3)
    findings = json.loads(args.findings) if args.findings else []
    if not isinstance(findings, list):
        die("--findings must be a JSON array", 1)
    step.update(
        {
            "status": "complete",
            "finished_at": now(),
            "output_path": args.output,
            "result": args.status,
            "findings": findings,
        }
    )
    state["current_step_id"] = None
    state["assigned_agent"] = None
    save_state(path, state)


def cmd_step_fail(args: argparse.Namespace) -> None:
    path = task_path(args.task_id)
    state = load_state(path)
    require_assigned(state, args.agent)
    step = find_current_step(state)
    if step["agent"] != args.agent:
        die(f"step {step['id']} is owned by {step['agent']}, not {args.agent}", 3)
    step.update(
        {
            "status": "failed",
            "finished_at": now(),
            "result": "fail",
            "failure_reason": args.reason,
        }
    )
    state["current_step_id"] = None
    state["assigned_agent"] = None
    save_state(path, state)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="task.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--task-id", required=True, help="e.g. task-01")

    sp = sub.add_parser("init", parents=[common])
    sp.add_argument("--description", required=True)
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("get", parents=[common])
    sp.set_defaults(func=cmd_get)

    sp = sub.add_parser("status", parents=[common])
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("assign", parents=[common])
    sp.add_argument("--agent", required=True)
    sp.set_defaults(func=cmd_assign)

    sp = sub.add_parser("release", parents=[common])
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--reason")
    sp.set_defaults(func=cmd_release)

    sp = sub.add_parser("step-start", parents=[common])
    sp.add_argument("--agent", required=True)
    sp.add_argument("--kind", required=True, help="e.g. confirm-intent, plan, implement, uat, security")
    sp.add_argument("--inputs-from", nargs="*", help="step ids this step depends on")
    sp.set_defaults(func=cmd_step_start)

    sp = sub.add_parser("step-complete", parents=[common])
    sp.add_argument("--agent", required=True)
    sp.add_argument("--status", required=True, choices=["pass", "partial", "fail"])
    sp.add_argument("--output", required=True, help="path to the agent's output markdown")
    sp.add_argument("--findings", help="JSON array of finding objects")
    sp.set_defaults(func=cmd_step_complete)

    sp = sub.add_parser("step-fail", parents=[common])
    sp.add_argument("--agent", required=True)
    sp.add_argument("--reason", required=True)
    sp.set_defaults(func=cmd_step_fail)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
