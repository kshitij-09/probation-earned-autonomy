# Probation: Earned Autonomy for AI Agents

A [Switch](https://switchagents.ai) workflow where a new AI agent joins a shared Slack channel of people and agents **as an intern** and earns autonomy **one task type at a time**.

Built for the **Flip the Switch hackathon**, Best Business Workflow track (4–7 Nov 2026).

## How it works

- Every action the worker agent proposes needs human sign-off, until it builds a clean record on that kind of task.
- After **3 consecutive clean approvals**, a task type (e.g. dependency bump) becomes autonomous.
- **One rejection or broken build** sends that task type back to approval-required.
- `auth/`, production config, and secrets **always** need a human, whatever the score.
- Tasks can come from people *or* peer agents; **only humans can approve**.
- A running report shows cost and human minutes saved per task type.

Gating is enforced in code (a Claude Code pre-action hook + a JSON trust ledger), not just in prompts.

## Participants

| Participant | Role |
|---|---|
| Human reviewer | Assigns tasks; the only one who can approve gated actions |
| Worker agent (Claude Code) | Takes tasks, proposes each action before acting |
| Supervisor agent | Keeps the trust ledger, gates actions, posts the ROI report |
| Peer agents | Assign tasks and receive results; cannot approve |

## This repository

It is both the **Probation tooling** and the **demo target** the worker agent operates on.

```
app/        tiny invoicing toolkit (demo code with planted problems)
tests/      pytest suite (some tests fail on purpose)
auth/       PROTECTED: always human-reviewed
config/     production.yaml is PROTECTED (fake values only)
probation/  ledger, hook, report, dashboard (in progress)
```

Planted work is filed as GitHub issues, labelled by task type:
`dependency-bump`, `test-fix`, `lint-fix`, `release-notes`, `small-feature`, `protected`.

All secrets in this repo are **fake**.

## Run locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/pytest -q
```

## Status

- [x] Switch server running locally, bridged to Slack
- [x] Demo repository and issues
- [ ] Worker fixes first issue after human approval
- [ ] Supervisor, trust ledger, enforcement hook
- [ ] Demotion, protected zone, ROI report, dashboard
- [ ] Demo video
