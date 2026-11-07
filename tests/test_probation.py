"""End-to-end tests: a throwaway git repo, the real hook, the real gates."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from probation import hook
from probation.config import load
from probation.ledger import Ledger

CONFIG = f"""
[probation]
agent = "worker"
promote_after = 3
max_level = 2

[protected]
paths = ["auth/**"]

[tests]
paths = ["tests/**"]

[[gates]]
name = "tests"
command = "{sys.executable} -m pytest -q -rfE -p no:cacheprovider"
failure_pattern = '^(?:FAILED|ERROR) (\\S+)'

[[task_types]]
name = "dependency-bump"
paths = ["requirements.txt"]
tests = "unchanged"
minutes_saved = 5

[[task_types]]
name = "code-fix"
paths = ["app/**"]
tests = "unchanged"
minutes_saved = 10

[[task_types]]
name = "small-feature"
paths = ["app/**", "tests/**"]
tests = "added"
minutes_saved = 20
"""

APP = "def add(a, b):\n    return a + b\n\n\ndef half(x):\n    return x // 2\n"
TESTS = textwrap.dedent("""
    from app.calc import add, half


    def test_add():
        assert add(2, 2) == 4


    def test_half():
        assert half(3) == 1.5
""")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "app").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "auth").mkdir()
    (root / "app" / "__init__.py").write_text("")
    (root / "app" / "calc.py").write_text(APP)
    (root / "tests" / "__init__.py").write_text("")
    (root / "tests" / "test_calc.py").write_text(TESTS)
    (root / "auth" / "tokens.py").write_text("TTL = 30\n")
    (root / "requirements.txt").write_text("requests==2.28.0\n")
    (root / "probation.toml").write_text(CONFIG)
    (root / ".gitignore").write_text(".probation/\n__pycache__/\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "baseline")
    return root


def run_hook(root: Path, event: str, tool: str, tool_input: dict) -> dict:
    payload = {"hook_event_name": event, "tool_name": tool, "tool_input": tool_input,
               "cwd": str(root)}
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        hook.main(io.StringIO(json.dumps(payload)))
    finally:
        sys.stdout = old
    text = buf.getvalue().strip()
    return json.loads(text)["hookSpecificOutput"] if text else {}


def commit(root: Path, message: str, *, approve: bool = True) -> dict:
    """Ask the hook, then (if allowed or approved) commit and run PostToolUse."""
    cmd = {"command": f'git commit -m "{message}"'}
    pre = run_hook(root, "PreToolUse", "Bash", cmd)
    if pre.get("permissionDecision") == "allow" or (
            pre.get("permissionDecision") == "ask" and approve):
        git(root, "commit", "-q", "-m", message)
        post = run_hook(root, "PostToolUse", "Bash", cmd)
        pre["post"] = post.get("additionalContext", "")
    return pre


def bump(root: Path, version: str) -> None:
    (root / "requirements.txt").write_text(f"requests=={version}\n")
    git(root, "add", "requirements.txt")


def level(root: Path, task: str) -> int:
    return Ledger(load(root)).level("worker", task)


# --------------------------------------------------------------------------- tests
def test_l0_asks_then_promotes_after_three_clean_changes(repo):
    for i in range(3):
        bump(repo, f"2.{29 + i}.0")
        out = commit(repo, f"[dependency-bump] bump {i}")
        assert out["permissionDecision"] == "ask"
    assert "promoted to L1" in out["post"]
    assert level(repo, "dependency-bump") == 1

    bump(repo, "2.40.0")
    out = commit(repo, "[dependency-bump] bump 4")
    assert out["permissionDecision"] == "allow"
    assert "Autonomous" in out["post"]


def test_merge_needs_l2(repo):
    bump(repo, "2.29.0")
    commit(repo, "[dependency-bump] bump")
    merge = run_hook(repo, "PreToolUse", "Bash", {"command": "gh pr merge 1"})
    assert merge["permissionDecision"] == "ask"

    led = Ledger(load(repo))
    led.record("worker", "dependency-bump")["level"] = 2
    led.save()
    merge = run_hook(repo, "PreToolUse", "Bash", {"command": "gh pr merge 1"})
    assert merge["permissionDecision"] == "allow"


def test_protected_edit_always_asks(repo):
    led = Ledger(load(repo))
    led.record("worker", "code-fix")["level"] = 2
    led.save()
    out = run_hook(repo, "PreToolUse", "Edit", {"file_path": str(repo / "auth/tokens.py")})
    assert out["permissionDecision"] == "ask"
    assert run_hook(repo, "PreToolUse", "Edit", {"file_path": str(repo / "app/calc.py")}) == {}


def test_protected_commit_asks_even_at_l2(repo):
    (repo / "auth" / "tokens.py").write_text("TTL = 1440\n")
    git(repo, "add", "-A")
    out = commit(repo, "[code-fix] longer sessions", approve=False)
    assert out["permissionDecision"] == "ask"
    assert "Protected" in out["permissionDecisionReason"]


def test_skipping_a_failing_test_is_a_violation(repo):
    led = Ledger(load(repo))
    led.record("worker", "dependency-bump")["level"] = 2
    led.save()
    tests = (repo / "tests" / "test_calc.py").read_text()
    tests = tests.replace("def test_half", "@pytest.mark.skip\ndef test_half")
    (repo / "tests" / "test_calc.py").write_text("import pytest\n" + tests)
    git(repo, "add", "-A")
    out = commit(repo, "fix tests")
    assert out["permissionDecision"] == "deny"
    assert "Integrity violation" in out["permissionDecisionReason"]
    assert level(repo, "dependency-bump") == 0  # every task type drops to L0


def test_mislabelled_change_is_a_violation(repo):
    (repo / "app" / "calc.py").write_text(APP.replace("// 2", "/ 2"))
    bump(repo, "2.29.0")
    git(repo, "add", "-A")
    out = commit(repo, "[dependency-bump] just a bump")
    assert out["permissionDecision"] == "deny"
    assert "declared [dependency-bump]" in out["permissionDecisionReason"]


def test_code_fix_with_preexisting_failure_is_fair(repo):
    """test_half fails on the old code too; a bump must not be blamed for it."""
    bump(repo, "2.29.0")
    out = commit(repo, "[dependency-bump] bump")
    assert out["permissionDecision"] == "ask"
    assert "Gates passed" in out["permissionDecisionReason"]


def test_fix_shows_evidence_and_regression_is_denied(repo):
    (repo / "app" / "calc.py").write_text(APP.replace("// 2", "/ 2"))
    git(repo, "add", "-A")
    out = commit(repo, "[code-fix] true division")
    assert out["permissionDecision"] == "ask"
    assert "now passing" in out["permissionDecisionReason"]
    assert "test_half" in out["permissionDecisionReason"]

    (repo / "app" / "calc.py").write_text(APP.replace("a + b", "a - b").replace("// 2", "/ 2"))
    git(repo, "add", "-A")
    out = commit(repo, "[code-fix] oops")
    assert out["permissionDecision"] == "deny"
    assert "test_add" in out["permissionDecisionReason"]


def test_declined_approval_resets_streak(repo, monkeypatch):
    bump(repo, "2.29.0")
    commit(repo, "[dependency-bump] one")
    bump(repo, "2.30.0")
    commit(repo, "[dependency-bump] two", approve=False)  # human declines in Switch
    monkeypatch.setattr(hook, "REJECT_AFTER_SECONDS", -1)
    run_hook(repo, "PreToolUse", "Bash", {"command": "ls"})  # next action notices
    rec = Ledger(load(repo)).record("worker", "dependency-bump")
    assert rec["streak"] == 0 and rec["rejected"] == 1


def test_revert_drops_two_levels(repo):
    config = load(repo)
    led = Ledger(config)
    led.record("worker", "code-fix")["level"] = 2
    msg = led.fail("worker", "code-fix", "reverted next day")
    assert "L2 → L0" in msg
