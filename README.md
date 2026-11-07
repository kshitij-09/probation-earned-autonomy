# Probation: earned autonomy for coding agents

**Your agents start as interns. They earn freedom one task type at a time, by making changes that pass your tests, and they lose it automatically when they slip.**

Probation is an open-source framework for teams who run AI coding agents in [Switch](https://switchagents.ai). Switch gives agents and people a shared Slack room and an approval button. Probation decides **when that button is needed**.

Built for the **Flip the Switch hackathon** (4–7 Nov 2026).

---

## What the demo shows

Recorded live in a Slack room through Switch, with a Claude Code worker agent fixing the planted issues in `examples/invoicer`:

| Step | What happened | Evidence |
|---|---|---|
| L0 | Every commit stopped for a Switch approval card; Probation showed the tests the fix made pass | [#15](https://github.com/kshitij-09/probation-earned-autonomy/pull/15), [#16](https://github.com/kshitij-09/probation-earned-autonomy/pull/16), [#17](https://github.com/kshitij-09/probation-earned-autonomy/pull/17) |
| Promotion | After 3 clean dependency bumps: `🎓 worker-agent promoted to L1 for dependency-bump` | [#18](https://github.com/kshitij-09/probation-earned-autonomy/pull/18) |
| L1 | The next bump committed and opened its PR with no approval: `🤖 Autonomous` | [#19](https://github.com/kshitij-09/probation-earned-autonomy/pull/19) |
| Judgement call | The worker stopped and asked before pinning a dependency that would break Python 3.10 | [#17](https://github.com/kshitij-09/probation-earned-autonomy/pull/17) |
| Demotion | A human reported a bad result; the supervisor dropped dependency-bump back to L0 | Demo video |
| Report | `@supervisor-agent report`: approvals, autonomous changes, minutes saved | Demo video |

In the demo the agents are named `worker-agent` and `supervisor-agent`; address them as `@worker-agent` and `@supervisor-agent`.

## The ladder

| Level | Name | What the agent can do | Who has the final say |
|---|---|---|---|
| **L0** | Supervised | Proposes a commit, then waits | A human, in a Switch approval card |
| **L1** | Draft PR | Commits and opens PRs on its own | A human merges |
| **L2** | Auto-merge | Commits and merges on its own when every gate passes | The tests |
| L3 | Audited | Autonomous, with random spot-checks | *Roadmap* |

Levels are kept **per agent and per task type**. An agent can be L2 for dependency bumps and still L0 for bug fixes. Login code, production config and secrets are **never** unlocked.

## How Probation decides

Every `git commit` an agent makes goes through a Claude Code hook. In order:

1. **What kind of change is this?** Probation works out the task type from the files touched, not from what the agent says. An agent may declare a type (`[dependency-bump]` in the commit message), but if the diff doesn't fit it, that's a **mislabel**.
2. **Did the agent weaken the tests?** Deleting test files, removing tests or assertions, or adding `skip`/`xfail` is an **integrity violation**.
3. **Do the gates pass?** Probation runs your tests and lint **itself**. A gate passes if it's green, or if it only fails the same way it already failed on the previous commit, so pre-existing or flaky failures aren't blamed on the agent. When a change makes failing tests pass, Probation shows them as **evidence**.
4. **Has the agent earned this?** At L0 the hook answers **ask**, and Switch shows an approval card in the room. At L1 and above it answers **allow**.

| What happened | Effect |
|---|---|
| 3 clean, test-checked changes of one type | **Promoted** one level for that type |
| A human declines in Switch | Clean streak resets |
| A landed change is reverted (`probation revert`) | That type drops **two levels** |
| Mislabel, test tampering | **All** task types back to L0 |
| Gate regression | Commit refused; the agent fixes it and retries |

Every decision is logged in `.probation/events.jsonl`, so you can always answer "why was this agent allowed to do that?".

## Where Switch comes in

| Probation says | Switch does |
|---|---|
| **allow** | The agent acts without asking, but only for task types it has earned |
| **ask** | Switch posts its approval request in the room; a human picks Allow or Decline |
| **deny** | The agent posts the reason in the room |

Promotions (`🎓 worker-agent promoted to L1 for dependency-bump`), demotions and violations are handed back to the agent, which posts them in the room, so the whole team watches trust being earned. The supervisor agent answers `@supervisor-agent report`.

Full setup, with room and agent instructions to paste: **[switch/README.md](switch/README.md)**.

## Quickstart

Requires Python 3.11+, git, and [Claude Code](https://claude.com/claude-code) as your agent.

```bash
git clone https://github.com/kshitij-09/probation-earned-autonomy.git
cd probation-earned-autonomy
pip install -e .
```

In **your own project**:

```bash
cd /path/to/your/project
probation init      # writes probation.toml, installs the hook in .claude/settings.json
probation status    # every task type starts at L0
```

Edit `probation.toml` to set your task types, protected paths and test commands. Then connect the agent to Switch ([switch/README.md](switch/README.md)).

Other commands:

```bash
probation report                          # approvals, autonomous changes, minutes saved
probation revert dependency-bump --reason "broke the build"
probation reject test-fix                 # a human asked for changes after the fact
probation reset                           # everyone back to L0
```

## Try it on the demo project

`examples/invoicer` is a small invoicing app with **deliberately planted problems**: out-of-date dependencies, two bugs with failing tests, lint errors, a missing feature, and a protected `auth/` folder. Each one is a labelled GitHub issue (#1–#13) for the worker agent to fix. **Its failing tests and lint errors are intentional.** File paths in the issues are relative to `examples/invoicer`.

```bash
cd examples/invoicer
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt -e ../..
.venv/bin/probation init
.venv/bin/probation status
```

Then point a Switch worker agent at `examples/invoicer` and ask it to fix issue #6.

## Repository layout

```
probation/           the framework (no dependencies beyond Python 3.11)
  classify.py        task type from the diff; catches mislabels
  gates.py           runs tests and lint against the previous commit; catches tampering
  ledger.py          levels per agent and task type, promotions, demotions, event log
  hook.py            Claude Code hook: allow / ask / deny, and outcome recording
  cli.py             probation init | status | report | revert | reject | reset
  template.toml      starting policy for `probation init`
switch/              Switch setup: room, worker and supervisor instructions
examples/invoicer/   demo project with planted issues
tests/               framework tests (pytest)
docs/                design write-up: "Agents that vouch for each other"
```

## Run the framework's tests

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
```

## Roadmap

The design goes further than this build. See [docs/blog-earned-autonomy-ladder.md](docs/blog-earned-autonomy-ladder.md).

- **L3 audited autonomy**, with random spot-checks that get rarer as the record grows
- **Trust between agents:** an L3 agent vouches for a newcomer and is demoted with it if the newcomer fails; agent approvals count for half
- A **7-day outcome window** (reverted or re-fixed lines count against a change)
- **Coverage of changed lines** as a gate, and a test-quality ceiling per folder
- A live **trust board** in the Switch room

## Known limits

- Gates run on the working tree, so stage everything you mean to commit.
- A declined approval is detected on the agent's next action; `probation reject` records it directly.
- The merge check uses the task type of the agent's latest commit.
