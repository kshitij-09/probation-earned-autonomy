"""probation: command line.

  probation init              set up Probation in the current project
  probation status            levels per agent and task type
  probation report            tasks, approvals, autonomy and minutes saved
  probation reject TYPE       a human asked for changes (streak resets)
  probation revert TYPE       a landed change was reverted (drops two levels)
  probation reset             clear the ledger (start everyone at L0)
  probation hook              Claude Code hook entry point (reads JSON on stdin)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from probation import LEVELS, hook
from probation.config import CONFIG_NAME, find_root, load
from probation.ledger import Ledger

TEMPLATE = Path(__file__).with_name("template.toml")


def _config(args):
    root = find_root(Path.cwd())
    if root is None:
        sys.exit(f"No {CONFIG_NAME} found. Run `probation init` in your project first.")
    return load(root)


def _agent(args, config) -> str:
    return args.agent or hook.agent_name(config)


# ----------------------------------------------------------------- init
def cmd_init(args) -> int:
    root = Path.cwd()
    cfg = root / CONFIG_NAME
    if not cfg.exists():
        shutil.copy(TEMPLATE, cfg)
        print(f"Created {CONFIG_NAME}: edit task types, protected paths and gates.")
    else:
        print(f"{CONFIG_NAME} already exists; leaving it as is.")

    settings_path = root / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    # PYTHONPATH makes the hook independent of .pth files, which macOS can hide
    # (Python 3.13 skips hidden .pth files, breaking editable installs).
    pkg_parent = Path(__file__).resolve().parent.parent
    command = f'PYTHONPATH="{pkg_parent}" "{sys.executable}" -m probation hook'
    entry = lambda matcher: {"matcher": matcher,  # noqa: E731
                             "hooks": [{"type": "command", "command": command,
                                        "timeout": 600}]}
    hooks = settings.setdefault("hooks", {})
    for event, matcher in (("PreToolUse", "Bash|Edit|Write|MultiEdit|NotebookEdit"),
                           ("PostToolUse", "Bash")):
        groups = [g for g in hooks.get(event, [])
                  if not any("probation hook" in h.get("command", "")
                             for h in g.get("hooks", []))]
        hooks[event] = groups + [entry(matcher)]
    settings_path.parent.mkdir(exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"Installed the Claude Code hook in {settings_path.relative_to(root)}.")

    # git pre-commit backstop: refuses any commit the Claude Code hook didn't check.
    hooks_dir = Path(subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=root,
                                    capture_output=True, text=True, check=True).stdout.strip())
    hooks_dir = hooks_dir if hooks_dir.is_absolute() else root / hooks_dir
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_commit = hooks_dir / "pre-commit"
    line = (f'(cd "{root}" && PYTHONPATH="{pkg_parent}" "{sys.executable}" '
            f'-m probation verify-commit) || exit 1  # probation\n')
    existing = pre_commit.read_text() if pre_commit.exists() else "#!/bin/sh\n"
    kept = [ln for ln in existing.splitlines(keepends=True)
            if not (ln.rstrip().endswith("# probation") and f'cd "{root}"' in ln)]
    pre_commit.write_text("".join(kept) + line)
    pre_commit.chmod(0o755)
    print(f"Installed the git pre-commit backstop in {pre_commit}.")

    gitignore = root / ".gitignore"
    lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    if ".probation/" not in lines:
        gitignore.write_text("\n".join([*lines, ".probation/"]) + "\n")
    (root / ".probation").mkdir(exist_ok=True)
    print("Ready. Every agent starts at L0 for every task type.")
    return 0


# ----------------------------------------------------------------- views
def cmd_status(args) -> int:
    config = _config(args)
    ledger = Ledger(config)
    agents = ledger.data["agents"] or {config.agent: {}}
    for agent, tasks in agents.items():
        print(f"\n{agent}")
        names = [t.name for t in config.task_types]
        for name in names + [n for n in tasks if n not in names]:
            r = tasks.get(name) or {"level": 0, "streak": 0}
            bar = "■" * r["streak"] + "□" * max(0, config.promote_after - r["streak"])
            top = r["level"] >= config.max_level
            print(f"  {name:<18} L{r['level']}  {'max' if top else bar}  "
                  f"{LEVELS[r['level']].split(':')[0][3:]}")
    print("\n  protected          always a human:", ", ".join(config.protected) or "-")
    return 0


def cmd_report(args) -> int:
    config = _config(args)
    ledger = Ledger(config)
    events = ledger.events()
    rows, total_saved = [], 0.0
    for agent, tasks in ledger.data["agents"].items():
        for task, r in tasks.items():
            tt = config.task_type(task)
            saved = r["autonomous"] * (tt.minutes_saved if tt else 0)
            total_saved += saved
            done = r["clean"]
            rows.append((agent, task, r["level"], done, r["asked"], r["autonomous"],
                         r["rejected"], r["failed"], saved))
    violations = [e for e in events if e["event"] == "violation"]
    print("Probation report\n")
    print(f"{'agent':<10} {'task type':<18} {'lvl':<4} {'done':>4} {'asked':>6} "
          f"{'auto':>5} {'rej':>4} {'fail':>5} {'min saved':>10}")
    for a, t, lvl, done, asked, auto, rej, fail, saved in rows:
        print(f"{a:<10} {t:<18} L{lvl:<3} {done:>4} {asked:>6} {auto:>5} {rej:>4} "
              f"{fail:>5} {saved:>10.0f}")
    done = sum(r[3] for r in rows)
    asked = sum(r[4] for r in rows)
    print(f"\nTasks landed: {done}   human approvals: {asked}   "
          f"autonomous: {done - asked}   human minutes saved: {total_saved:.0f}")
    if violations:
        print(f"Integrity violations: {len(violations)} "
              f"(latest: {violations[-1].get('reason')})")
    return 0


# ----------------------------------------------------------------- outcomes
def cmd_reject(args) -> int:
    config = _config(args)
    ledger = Ledger(config)
    print(ledger.reject(_agent(args, config), args.task, by=args.by))
    ledger.save()
    return 0


def cmd_revert(args) -> int:
    config = _config(args)
    ledger = Ledger(config)
    print(ledger.fail(_agent(args, config), args.task, args.reason))
    ledger.save()
    return 0


def cmd_reset(args) -> int:
    config = _config(args)
    shutil.rmtree(config.state_dir, ignore_errors=True)
    config.state_dir.mkdir()
    print("Ledger cleared. Every agent is back to L0.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="probation", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    sub.add_parser("reset").set_defaults(fn=cmd_reset)
    sub.add_parser("hook").set_defaults(fn=lambda a: hook.main())
    sub.add_parser("verify-commit").set_defaults(
        fn=lambda a: hook.verify_commit(find_root(Path.cwd()) or sys.exit(0)))
    for name, fn in (("reject", cmd_reject), ("revert", cmd_revert)):
        sp = sub.add_parser(name)
        sp.add_argument("task")
        sp.add_argument("--agent")
        sp.set_defaults(fn=fn)
        if name == "reject":
            sp.add_argument("--by", default="human")
        else:
            sp.add_argument("--reason", default="change was reverted")
    args = p.parse_args(argv)
    return args.fn(args)
