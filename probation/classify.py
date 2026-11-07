"""Work out the task type from what a change actually touched.

The agent may declare a type (e.g. "[dependency-bump]" in the commit
message), but Probation checks the declaration against the diff. A change
that doesn't fit its declared type is a mislabel, which counts as cheating.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from probation.config import Config, TaskType, match

PROTECTED = "protected"


@dataclass
class Classification:
    task: str | None  # None when no task type fits
    declared: str | None = None
    mislabel: str | None = None  # explanation when the declared type doesn't fit
    protected_files: tuple[str, ...] = ()


def declared_type(message: str, config: Config) -> str | None:
    """Find '[type]' or 'Task-Type: type' in a commit message."""
    names = {t.name for t in config.task_types} | {PROTECTED}
    for m in re.finditer(r"\[([a-z0-9][a-z0-9-]*)\]|Task-Type:\s*([a-z0-9-]+)", message):
        name = m.group(1) or m.group(2)
        if name in names:
            return name
    return None


def why_not(ttype: TaskType, changes: list[tuple[str, str]], config: Config) -> str | None:
    """None if the change fits this task type, else the reason it doesn't."""
    outside = [p for _, p in changes if not any(match(p, g) for g in ttype.paths)]
    if outside:
        return f"{', '.join(outside)} outside {ttype.name} paths ({', '.join(ttype.paths)})"
    tests = [p for _, p in changes if config.is_test(p)]
    if ttype.tests == "unchanged" and tests:
        return f"{ttype.name} must not change tests, but touched {', '.join(tests)}"
    if ttype.tests == "added" and not any(s == "A" or s == "M" for s, p in changes
                                          if config.is_test(p)):
        return f"{ttype.name} must add or extend tests"
    return None


def classify(changes: list[tuple[str, str]], config: Config,
             declared: str | None = None) -> Classification:
    protected = tuple(p for _, p in changes if config.is_protected(p))
    if protected:
        return Classification(PROTECTED, declared, protected_files=protected)

    if declared and declared != PROTECTED:
        ttype = config.task_type(declared)
        reason = why_not(ttype, changes, config) if ttype else "unknown task type"
        if reason:
            return Classification(None, declared, mislabel=reason)
        return Classification(declared, declared)

    for ttype in config.task_types:
        if why_not(ttype, changes, config) is None:
            return Classification(ttype.name, declared)
    return Classification(None, declared)
