"""Small git helpers. All paths are relative to the Probation root."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git(root: Path, *args: str, check: bool = True) -> str:
    out = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    if check and out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def head(root: Path) -> str | None:
    out = git(root, "rev-parse", "HEAD", check=False).strip()
    return out or None


def staged_changes(root: Path) -> list[tuple[str, str]]:
    """(status, path) for every staged file under root. Status is A, M or D."""
    out = git(root, "diff", "--cached", "--name-status", "--no-renames", "--relative")
    changes = []
    for line in out.splitlines():
        status, _, path = line.partition("\t")
        if path:
            changes.append((status[0], path))
    return changes


def show(root: Path, rev: str, path: str) -> str:
    """File content at rev ('HEAD') or in the index (rev='')."""
    return git(root, "show", f"{rev}:./{path}", check=False)
