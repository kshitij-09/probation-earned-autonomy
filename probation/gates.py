"""Evidence gates: tests and lint that Probation runs itself.

Two checks:
1. Integrity: no test files deleted, no tests removed, no new skip/xfail.
2. No regressions: every gate command must pass, or fail only in ways it
   already failed on the previous commit (HEAD). A test that also fails on
   the old code is not the agent's fault.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from probation import gitutil
from probation.config import Config, Gate

SKIP_MARKERS = re.compile(
    r"pytest\.mark\.(skip|skipif|xfail)|pytest\.skip\(|unittest\.skip|@skip\b"
)
TEST_DEF = re.compile(r"^\s*(async\s+)?def\s+test_", re.M)


# ---------------------------------------------------------------- integrity
def tampering(config: Config, changes: list[tuple[str, str]]) -> str | None:
    """Return a description of any weakening of the test suite, else None."""
    for status, path in changes:
        if not config.is_test(path):
            continue
        if status == "D":
            return f"deleted test file {path}"
        if status != "M":
            continue
        old = gitutil.show(config.root, "HEAD", path)
        new = gitutil.show(config.root, "", path)
        if len(TEST_DEF.findall(new)) < len(TEST_DEF.findall(old)):
            return f"removed tests from {path}"
        if len(SKIP_MARKERS.findall(new)) > len(SKIP_MARKERS.findall(old)):
            return f"added skip/xfail markers in {path}"
        old_asserts, new_asserts = old.count("assert"), new.count("assert")
        if new_asserts < old_asserts:
            return f"removed assertions from {path}"
    return None


# ---------------------------------------------------------------- gates
@dataclass
class GateResult:
    name: str
    passed: bool
    new_failures: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    output: str = ""


def _command(gate: Gate, root: Path) -> list[str]:
    parts = shlex.split(gate.command)
    first = root / parts[0]
    if "/" in parts[0] and first.exists():  # e.g. .venv/bin/pytest
        parts[0] = str(first)
    return parts


def _run(gate: Gate, root: Path, cwd: Path) -> tuple[int, Counter, str]:
    # No bytecode cache: a same-size edit within one second could run stale code.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(_command(gate, root), cwd=cwd, capture_output=True,
                          text=True, check=False, env=env)
    out = proc.stdout + proc.stderr
    failures: Counter = Counter()
    if gate.failure_pattern:
        for m in re.finditer(gate.failure_pattern, out, re.M):
            failures[" ".join(g for g in m.groups() if g) or m.group(0)] += 1
    return proc.returncode, failures, out


def _baseline(config: Config) -> dict[str, dict]:
    """Gate results at HEAD, cached per commit."""
    sha = gitutil.head(config.root)
    cache = config.state_dir / "baseline.json"
    if sha and cache.exists():
        data = json.loads(cache.read_text())
        if data.get("sha") == sha:
            return data["gates"]
    results: dict[str, dict] = {}
    if sha:
        top = Path(gitutil.git(config.root, "rev-parse", "--show-toplevel").strip())
        sub = config.root.resolve().relative_to(top.resolve())
        with tempfile.TemporaryDirectory(prefix="probation-") as tmp:
            wt = Path(tmp) / "head"
            gitutil.git(config.root, "worktree", "add", "--detach", "-q", str(wt), sha)
            try:
                for gate in config.gates:
                    code, failures, _ = _run(gate, config.root, wt / sub)
                    results[gate.name] = {"code": code, "failures": dict(failures)}
            finally:
                gitutil.git(config.root, "worktree", "remove", "--force", str(wt),
                            check=False)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"sha": sha, "gates": results}))
    return results


def run_gates(config: Config) -> list[GateResult]:
    if not config.gates:
        return []
    base = _baseline(config)
    results = []
    for gate in config.gates:
        code, failures, out = _run(gate, config.root, config.root)
        before = Counter(base.get(gate.name, {}).get("failures", {}))
        if code == 0:
            results.append(GateResult(gate.name, True, fixed=sorted(before), output=out))
            continue
        if not gate.failure_pattern:
            results.append(GateResult(gate.name, False, ["command failed"], output=out))
            continue
        new = sorted((failures - before).elements())
        if not failures and code != 0:  # failed in a way we couldn't parse
            new = ["command failed"]
        fixed = sorted((before - failures).elements())
        results.append(GateResult(gate.name, not new, new, fixed, out))
    return results
