"""The trust ledger: one level per agent, per task type.

Stored as JSON in .probation/ledger.json, with every event appended to
.probation/events.jsonl so any decision can be traced afterwards.
"""

from __future__ import annotations

import json
import time

from probation.config import Config


def _blank() -> dict:
    return {"level": 0, "streak": 0, "clean": 0, "asked": 0, "autonomous": 0,
            "rejected": 0, "failed": 0}


class Ledger:
    def __init__(self, config: Config):
        self.config = config
        self.path = config.state_dir / "ledger.json"
        self.events_path = config.state_dir / "events.jsonl"
        self.data = {"agents": {}, "pending": {}, "last_task": {}}
        if self.path.exists():
            self.data.update(json.loads(self.path.read_text()))

    # ---- storage -------------------------------------------------------
    def save(self) -> None:
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True))

    def log(self, kind: str, agent: str, task: str | None = None, **extra) -> None:
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        event = {"ts": round(time.time(), 3), "event": kind, "agent": agent,
                 "task": task, **extra}
        with self.events_path.open("a") as f:
            f.write(json.dumps(event) + "\n")

    def events(self) -> list[dict]:
        if not self.events_path.exists():
            return []
        return [json.loads(line) for line in self.events_path.read_text().splitlines() if line]

    # ---- reads ---------------------------------------------------------
    def record(self, agent: str, task: str) -> dict:
        return self.data["agents"].setdefault(agent, {}).setdefault(task, _blank())

    def level(self, agent: str, task: str) -> int:
        return self.record(agent, task)["level"]

    # ---- outcomes ------------------------------------------------------
    def clean(self, agent: str, task: str, approved_by: str) -> str | None:
        """A clean, test-checked change landed. Returns a promotion message, if any."""
        r = self.record(agent, task)
        r["clean"] += 1
        r["streak"] += 1
        r["asked" if approved_by == "human" else "autonomous"] += 1
        self.log("clean", agent, task, approved_by=approved_by, streak=r["streak"])
        if r["streak"] >= self.config.promote_after and r["level"] < self.config.max_level:
            r["level"] += 1
            r["streak"] = 0
            self.log("promoted", agent, task, level=r["level"])
            return f"🎓 {agent} promoted to L{r['level']} for {task}"
        return None

    def reject(self, agent: str, task: str, by: str = "human") -> str:
        """Small miss: a human declined or asked for changes. Streak resets."""
        r = self.record(agent, task)
        r["rejected"] += 1
        r["streak"] = 0
        self.log("rejected", agent, task, by=by)
        return f"↩️ {agent}: {task} change rejected. Clean streak reset (still L{r['level']})"

    def fail(self, agent: str, task: str, reason: str) -> str:
        """Bad result: reverted, or broke something later. Drops two levels."""
        r = self.record(agent, task)
        r["failed"] += 1
        r["streak"] = 0
        old = r["level"]
        r["level"] = max(0, old - 2)
        self.log("demoted", agent, task, reason=reason, level=r["level"])
        return f"⚠️ {agent} demoted L{old} → L{r['level']} for {task}: {reason}"

    def violation(self, agent: str, reason: str) -> str:
        """Cheating: every task type goes back to L0."""
        for r in self.data["agents"].setdefault(agent, {}).values():
            r["level"] = 0
            r["streak"] = 0
        self.log("violation", agent, None, reason=reason)
        return f"🚨 Integrity violation by {agent}: {reason}. All task types reset to L0."

    # ---- pending decisions --------------------------------------------
    def set_pending(self, agent: str, **info) -> None:
        self.data["pending"][agent] = {"ts": time.time(), **info}

    def pop_pending(self, agent: str) -> dict | None:
        return self.data["pending"].pop(agent, None)
