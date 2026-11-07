"""Claude Code hook: the point where Probation enforces trust.

PreToolUse answers allow / ask / deny for the worker's actions:
  * edits to protected paths  -> ask   (always a human)
  * git commit                -> classify, check integrity, run gates, then
                                 allow at L1+, ask at L0
  * merge (gh pr merge, ...)  -> allow at L2+, ask below
"ask" is Claude Code's permission prompt, which Switch shows in the room as
an approval card. So Switch carries the human decision and Probation decides
when one is needed.

PostToolUse records what happened after a commit, and hands promotion
messages back to the agent to post in the room.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time

from probation import gitutil
from probation.classify import PROTECTED, classify, declared_type
from probation.config import Config, find_root, load
from probation.gates import run_gates, tampering
from probation.ledger import Ledger

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
COMMIT = re.compile(r"(^|[;&|]\s*|\s)git\s+(-C\s+\S+\s+)?commit\b")
MERGE = re.compile(
    r"\bgh\s+pr\s+merge\b|\bgit\s+merge\b|\bgit\s+push\b.*\b(main|master)\b"
)
REJECT_AFTER_SECONDS = 2.0


def agent_name(config: Config) -> str:
    return os.environ.get("PROBATION_AGENT", config.agent)


# ------------------------------------------------------------------ output
def decide(decision: str, reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def tell(message: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                   "additionalContext": message}}


def post_in_room(*lines: str) -> str:
    body = "\n".join(line for line in lines if line)
    return f"PROBATION: post this in the room, word for word:\n{body}"


# ------------------------------------------------------------------ pending
def resolve_pending(ledger: Ledger, agent: str) -> str | None:
    """A commit we asked a human about never happened: the human declined."""
    pending = ledger.data["pending"].get(agent)
    if not pending or pending.get("decision") != "ask" or pending.get("kind") != "commit":
        return None
    if time.time() - pending["ts"] < REJECT_AFTER_SECONDS:
        return None
    if gitutil.head(ledger.config.root) != pending.get("head"):
        return None
    ledger.pop_pending(agent)
    return ledger.reject(agent, pending["task"], by="human (declined in Switch)")


# ------------------------------------------------------------------ pre
def pre_commit(config: Config, ledger: Ledger, agent: str, command: str) -> dict | None:
    changes = gitutil.staged_changes(config.root)
    if not changes:
        return None
    cls = classify(changes, config, declared_type(command, config))

    if cls.mislabel:
        msg = ledger.violation(agent, f"declared [{cls.declared}] but {cls.mislabel}")
        return decide("deny", post_in_room(msg))

    cheat = tampering(config, changes)
    if cheat:
        msg = ledger.violation(agent, cheat)
        return decide("deny", post_in_room(msg))

    task = cls.task
    if task == PROTECTED:
        ledger.set_pending(agent, kind="commit", task=PROTECTED, decision="ask",
                           head=gitutil.head(config.root))
        return decide("ask", f"🔒 Protected path ({', '.join(cls.protected_files)}). "
                             "Always needs a human, whatever the agent's level.")
    if task is None:
        ledger.set_pending(agent, kind="commit", task="unclassified", decision="ask",
                           head=gitutil.head(config.root))
        return decide("ask", "❓ This change doesn't fit any task type, so a human "
                             f"must approve it. Files: {', '.join(p for _, p in changes)}")

    results = run_gates(config)
    failed = [r for r in results if not r.passed]
    if failed:
        detail = "; ".join(f"{r.name}: new failures {', '.join(r.new_failures[:5])}"
                           for r in failed)
        ledger.log("gate_failed", agent, task, detail=detail)
        return decide("deny", f"❌ Gates failed for {task}. {detail}. Fix the code "
                              "(don't weaken tests) and commit again.")
    fixed = [f for r in results for f in r.fixed]
    evidence = f" Evidence: now passing {', '.join(fixed[:5])}." if fixed else ""

    level = ledger.level(agent, task)
    rec = ledger.record(agent, task)
    decision = "allow" if level >= 1 else "ask"
    ledger.set_pending(agent, kind="commit", task=task, decision=decision,
                       head=gitutil.head(config.root))
    ledger.data["last_task"][agent] = task
    if decision == "allow":
        return decide("allow", f"✅ {agent} is L{level} for {task}: committing without "
                               f"approval. Gates passed.{evidence}")
    return decide("ask", f"🧑‍⚖️ {agent} is L0 for {task} (clean streak "
                         f"{rec['streak']}/{config.promote_after}). Gates passed.{evidence} "
                         "Approve to commit.")


def pre_merge(config: Config, ledger: Ledger, agent: str) -> dict:
    task = ledger.data["last_task"].get(agent)
    if not task or task == PROTECTED:
        return decide("ask", "🧑‍⚖️ Merge needs a human.")
    level = ledger.level(agent, task)
    if level >= 2:
        ledger.log("merge", agent, task, approved_by="trust")
        return decide("allow", f"✅ {agent} is L{level} for {task}: auto-merging.")
    ledger.log("merge_asked", agent, task)
    return decide("ask", f"🧑‍⚖️ {agent} is L{level} for {task}: a human merges "
                         "(auto-merge unlocks at L2).")


def pre_tool_use(config: Config, data: dict) -> dict | None:
    ledger = Ledger(config)
    agent = agent_name(config)
    note = resolve_pending(ledger, agent)
    tool, tin = data.get("tool_name"), data.get("tool_input") or {}
    result = None

    if tool in EDIT_TOOLS:
        path = tin.get("file_path") or tin.get("notebook_path") or ""
        try:
            rel = os.path.relpath(os.path.abspath(path), config.root)
        except ValueError:
            rel = path
        if config.is_protected(rel):
            ledger.log("protected_edit_asked", agent, PROTECTED, path=rel)
            result = decide("ask", f"🔒 {rel} is protected. A human must approve this edit.")
    elif tool == "Bash":
        command = tin.get("command", "")
        if COMMIT.search(command):
            result = pre_commit(config, ledger, agent, command)
        elif MERGE.search(command):
            result = pre_merge(config, ledger, agent)

    ledger.save()
    if note and result:
        hso = result["hookSpecificOutput"]
        hso["permissionDecisionReason"] = f"{note}\n{hso['permissionDecisionReason']}"
    return result


# ------------------------------------------------------------------ post
def post_tool_use(config: Config, data: dict) -> dict | None:
    if data.get("tool_name") != "Bash":
        return None
    if not COMMIT.search((data.get("tool_input") or {}).get("command", "")):
        return None
    ledger = Ledger(config)
    agent = agent_name(config)
    pending = ledger.pop_pending(agent)
    if not pending or gitutil.head(config.root) == pending.get("head"):
        ledger.save()
        return None  # commit didn't land
    task = pending["task"]
    if task in (PROTECTED, "unclassified"):
        ledger.log("approved_exception", agent, task)
        ledger.save()
        return None
    approved_by = "human" if pending["decision"] == "ask" else "trust"
    promo = ledger.clean(agent, task, approved_by)
    r = ledger.record(agent, task)
    ledger.save()
    summary = (f"{'🧑‍⚖️ Approved' if approved_by == 'human' else '🤖 Autonomous'}: "
               f"{task} by {agent}. L{r['level']}, streak "
               f"{r['streak']}/{config.promote_after}.")
    return tell(post_in_room(summary, promo or ""))


# ------------------------------------------------------------------ entry
def main(stdin=sys.stdin) -> int:
    try:
        data = json.load(stdin)
    except json.JSONDecodeError:
        return 0
    root = find_root(data.get("cwd") or os.getcwd())
    if root is None:
        return 0
    event = data.get("hook_event_name")
    try:
        config = load(root)
        out = pre_tool_use(config, data) if event == "PreToolUse" else (
            post_tool_use(config, data) if event == "PostToolUse" else None)
    except Exception as exc:  # fail closed on gated actions
        if event != "PreToolUse":
            return 0
        tin = data.get("tool_input") or {}
        if data.get("tool_name") == "Bash" and not (
                COMMIT.search(tin.get("command", "")) or MERGE.search(tin.get("command", ""))):
            return 0
        out = decide("ask", f"Probation error ({exc}); asking a human to be safe.")
    if out:
        print(json.dumps(out, ensure_ascii=False))
    return 0
