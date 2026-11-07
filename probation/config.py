"""Load probation.toml, the per-project policy."""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_NAME = "probation.toml"


@dataclass
class TaskType:
    name: str
    paths: list[str]
    tests: str = "any"  # "unchanged" | "added" | "any"
    minutes_saved: float = 5.0


@dataclass
class Gate:
    name: str
    command: str
    failure_pattern: str | None = None


@dataclass
class Config:
    root: Path
    agent: str = "worker"
    promote_after: int = 3
    max_level: int = 2
    protected: list[str] = field(default_factory=list)
    test_paths: list[str] = field(default_factory=lambda: ["tests/**"])
    gates: list[Gate] = field(default_factory=list)
    task_types: list[TaskType] = field(default_factory=list)

    @property
    def state_dir(self) -> Path:
        return self.root / ".probation"

    def task_type(self, name: str) -> TaskType | None:
        return next((t for t in self.task_types if t.name == name), None)

    def is_protected(self, path: str) -> bool:
        return any(match(path, p) for p in self.protected)

    def is_test(self, path: str) -> bool:
        return any(match(path, p) for p in self.test_paths)


def match(path: str, pattern: str) -> bool:
    """Glob match where '*' may cross folders and '**/' may match nothing."""
    if path.startswith("./"):
        path = path[2:]
    if fnmatch.fnmatch(path, pattern):
        return True
    return pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:])


def find_root(start: str | Path) -> Path | None:
    """Walk up from start to the folder that holds probation.toml."""
    p = Path(start).resolve()
    for d in [p, *p.parents]:
        if (d / CONFIG_NAME).is_file():
            return d
    return None


def load(root: Path) -> Config:
    raw = tomllib.loads((root / CONFIG_NAME).read_text())
    core = raw.get("probation", {})
    return Config(
        root=root,
        agent=core.get("agent", "worker"),
        promote_after=int(core.get("promote_after", 3)),
        max_level=min(int(core.get("max_level", 2)), 3),
        protected=list(raw.get("protected", {}).get("paths", [])),
        test_paths=list(raw.get("tests", {}).get("paths", ["tests/**"])),
        gates=[Gate(**g) for g in raw.get("gates", [])],
        task_types=[TaskType(**t) for t in raw.get("task_types", [])],
    )
