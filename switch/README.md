# Running Probation in Switch

Switch is where the people and agents work together. Probation decides **when a human is needed**; Switch is **where that human sees the request and answers it**.

```
 Slack room (via Switch)                    Worker agent (Claude Code)
 ─────────────────────────                  ──────────────────────────
 human / triage agent: "fix #6"  ───────▶   edits code, runs `git commit`
                                                      │
                                            Probation hook (PreToolUse)
                                            classify → integrity → gates → ledger
                                                      │
              ┌───────────────────────────────────────┼──────────────────────┐
           allow (L1+)                            ask (L0)                deny
              │                                       │                     │
   commit runs, agent posts            Switch approval card in the room     agent is told why
   "🤖 Autonomous: …"                  human: Allow / Decline              (gate failed, cheating)
                                                      │
                                       Probation hook (PostToolUse)
                                       records the outcome, may promote
                                       agent posts "🎓 promoted to L1 …"
```

The hook's three answers map onto what Switch already does:

| Probation says | What happens in Switch |
|---|---|
| **allow** | The agent acts without asking, as if "act without asking" were on, but only for this task type |
| **ask** | Switch posts its approval request in the room; a human chooses Allow or Decline |
| **deny** | The action is refused and the agent explains why in the room |

## Setup (about 10 minutes)

1. **Run Switch** (Switch Console with a local server) and connect your Slack workspace.
2. **Create a room** for the repo, e.g. `#earned-autonomy`. Paste [`room-instructions.md`](room-instructions.md) into the room instructions.
3. **Create the worker agent** (Claude Code) with its working folder set to your project (for the demo: `examples/invoicer`). Paste [`worker.md`](worker.md) into its instructions. Set *Who can instruct this agent* to **Me and my agents**, so a triage agent can hand it work.
4. **Create the supervisor agent** (Claude Code, same folder). Paste [`supervisor.md`](supervisor.md) into its instructions. Give it the `@supervisor` role.
5. In the project folder, run `probation init`. This installs the hook into `.claude/settings.json`, which the worker's Claude Code picks up.
6. Leave the worker's **"act without asking" setting off**. Probation turns on autonomy per task type when it's earned.

## Try it

In the room:

```
@worker please fix issue #6 (discount rounding)
```

The worker fixes the code and tries to commit. Probation runs the tests, sees two previously failing tests now pass, and, because the worker is at L0 for `test-fix`, Switch shows an approval request. Approve it. The worker posts `🧑‍⚖️ Approved: test-fix by worker. L0, streak 1/3.`

After three clean changes of one type the worker posts `🎓 worker promoted to L1 for …`, and the next change of that type commits without asking.

```
@supervisor report
```

posts levels, approvals, autonomous changes and minutes saved.
