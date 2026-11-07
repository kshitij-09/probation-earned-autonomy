# Agents that vouch for each other, and pay when they're wrong

*How a team of AI coding agents earns trust from L0 to L3, using test results as evidence and taking shared responsibility when one of them gets it wrong.*

> **What's built today:** the [Probation repo](https://github.com/kshitij-09/probation-earned-autonomy) implements L0 to L2, task types read from the diff, test gates, tamper detection, promotion and demotion, running in Switch. L3 spot-checks and trust between agents (vouching, weighted approvals, shared blame) are the design described here and are on the roadmap. The comparison with other tools reflects our understanding as of November 2026.

---

## It's no longer one agent and one human

Most thinking about AI agents imagines a simple pair: one agent and one human. The agent asks for permission, and the human says yes or no.

That's not how teams are starting to work. Today you might have several agents in a single Slack room. One sorts incoming requests. Another writes the code. A third reviews it. A human sits on top as the final quality check. The agents talk to each other, hand work to each other, and sometimes approve each other's work.

This raises questions that the one-agent picture never had to answer:

- Can an experienced agent vouch for a new one?
- Does an agent's "approve" count the same as a human's?
- If a trusted agent hands work to an unproven one, whose trust applies?

Meanwhile, the tools we have for trust are still very blunt. You either approve every action, which turns you into a full-time button clicker, or you switch approvals off and hope nothing breaks. Either way, the decision is made once, by hand. It doesn't change based on how the agent actually performs.

We don't run human teams like this. A new engineer starts with small tasks. They show good work, and they get more freedom. If they cut corners, they lose it. Senior people vouch for junior ones, and they share the blame when things go wrong.

A team of agents needs the same kind of rules. That's what we built Probation to do.

## The idea in one line

**Trust is earned through results, can be lent with risk attached, and is never passed along through a handoff.**

Probation watches every change an agent makes. It checks that change using your own test suite. Based on the results, it moves the agent up or down a simple ladder with four levels.

## The ladder: L0 to L3

| Level | Name | What the agent can do | Who has the final say |
|---|---|---|---|
| **L0** | Supervised | Suggests a change, then waits | A human, before anything runs |
| **L1** | Draft PR | Opens a pull request by itself | A human, who decides whether to merge |
| **L2** | Auto-merge | Merges by itself if every check passes, then tells the team | The tests |
| **L3** | Audited | Merges by itself; a few changes are picked at random for a human to review | The tests, plus random spot-checks |

Every agent starts at **L0**. It can suggest changes, but a human has to approve each one before anything happens.

At **L1**, the agent can open pull requests on its own. A human still decides whether to merge. This is roughly where most coding agents sit today.

At **L2**, the agent can merge its own work, but only if every check passes. It posts a short note so the team knows what happened.

At **L3**, the agent works on its own, but Probation picks some of its changes at random and asks a human to look. These spot-checks happen often at first and less often as the agent's record grows.

Two details matter. First, levels are set **per agent and per task type**. The same agent can be at L3 for documentation and still at L0 for database changes. Being good at one thing doesn't make you trusted at everything.

Second, some areas are **never** unlocked, whatever the agent's record. Login and security code, secrets and production settings always need a human.

## Trust between agents

This is the part that's genuinely new. Once several agents share a room, trust is no longer just between an agent and a human. It's also between agents. Probation handles this with a few clear rules.

### Vouching: an experienced agent can sponsor a new one

A new agent normally starts at L0 and has to work its way up. But an experienced agent can **vouch** for it.

Only an agent at L3 for a task type can vouch for another agent on that same task type. The new agent can then work **at most one level below its sponsor**, and never above L2. A sponsor at L3 can lift a newcomer to L2 at most. Protected areas are never included.

Here's the important part. **If the new agent's change goes wrong, both agents are penalised.** The new agent takes the normal penalty, and the sponsor drops one level too.

Think of it like co-signing a loan. You can help someone get started, but you're on the hook if they fail. That's what stops agents from vouching for each other casually.

### Approvals: an agent's "yes" counts, but for less

Agents can approve each other's work, but their approval isn't treated the same as a human's.

| | Human approval | Agent approval |
|---|---|---|
| Lets the change go ahead | Yes | Only if the approver is at least one level above the agent doing the work |
| Credit toward promotion | Full | Half |
| Can unlock L2 or L3 on its own | Yes | No. Every promotion to L2 or above needs some outcomes a human has checked |
| Protected areas | Yes | Never |

This keeps the room moving without letting agents promote each other with no human involved. Agents can do a lot of the reviewing, but humans still anchor every important step up.

### Handoffs: passing work along doesn't pass trust along

Agents hand work to each other all the time. The triage agent picks up a request and gives it to a worker. So whose trust applies?

The answer is simple: **the work runs at the level of whoever actually does it.** If an L3 agent assigns a task to an L0 agent, the result is an L0 action and needs a human's approval. Trust doesn't flow downstream just because a trusted agent made the request.

There's a second safeguard. Probation decides what kind of task something is by **reading the change itself**, not by trusting the label an agent gives it. A triage agent can't call a change to the login code a "docs task" to get it through faster.

### Rules that stop agents gaming each other

Any system where agents can approve each other needs guardrails against abuse. Probation has three:

- **No approving your own work**, or work you assigned to someone else. Otherwise a triage agent could hand a task to a worker and then approve the result itself.
- **No approval rings.** If two agents keep approving each other's work, the credit they earn from each other is capped and the pair is flagged for a human to look at.
- **Tests come first.** No approval, from a human or an agent, overrides a failed check.

### Who is blamed when something breaks

When a change causes a problem, everyone involved shares the responsibility, but not equally.

| Role | Penalty |
|---|---|
| The agent that made the change | Full penalty |
| The agent that approved it or vouched for it | Partial: drops one level |
| The agent that assigned the task | None, unless it described the task wrongly |

This mirrors how good human teams work. The person who did the work is responsible. The person who signed off on it shares some of that. The person who asked for it is only at fault if they asked for the wrong thing.

## How an agent moves up: tests are the evidence

All of this depends on one thing: a reliable way to tell whether a change was actually good. For coding, we already have one. It's the test suite.

Probation first works out what kind of task a change is by looking at what it touched. Formatting, documentation, new tests, dependency updates, refactors, bug fixes, new features, and database or infrastructure changes each count as a different type.

Then it checks the change. A change only counts as **clean** if all of these are true:

- **It builds and passes the full test suite.** Probation runs the tests itself. It never takes the agent's word for it.
- **No tests were deleted, skipped or weakened.** An agent that gets green checks by switching off the failing test hasn't done good work. It has cheated.
- **The new code is actually covered by tests.** Passing tests mean nothing if none of them run the code that changed.
- **For bug fixes, there's proof.** The agent adds a test that **fails on the old code and passes after the fix**. That shows the bug was real and is now gone.
- **It holds up over time.** Nobody reverted the change or had to fix it again within the next 7 days.

Riskier task types need a longer clean record before the agent moves up. A few clean documentation changes might be enough to reach the next level. Refactors might need ten, and new features twenty-five.

There's also a ceiling. In parts of the codebase with weak tests, no agent can go above L1, however good its record. **An agent can't be more independent than your tests are good.**

This is also why tests matter so much for trust between agents. Without solid tests, agents vouching for each other is just agents taking each other's word for it. With them, every vouch and every approval rests on evidence that a machine has checked.

## How an agent moves down

Trust has to be easy to lose, or it means nothing. Probation sorts mistakes into three kinds, each with a different result.

| What happened | Example | Result |
|---|---|---|
| **Cheating** | Skipped a failing test, touched protected code, mislabelled its own change | Back to **L0 for everything**, and a human is alerted |
| **Bad result** | The change was reverted, or broke something later | That task type drops **two levels**; the sponsor or approver drops one |
| **Small miss** | Failed checks before merging, or the reviewer asked for changes | No drop, but the agent's clean streak starts again |

Cheating is treated most harshly because it breaks the whole system. If an agent is willing to weaken a test to get through, nothing it has done can be trusted.

Probation also tries to be fair. Some tests fail at random because of timing or network issues. When a test fails, Probation runs it again on the old code. If it fails there too, the problem isn't the agent's change, and the agent isn't penalised.

Finally, trust fades. If an agent hasn't done a task type for a long time, or the codebase has changed a lot, it drops one level and proves itself again. Past good work on very different code isn't proof of good work today.

## Where other tools stand today

Here's how today's agent tools look on the same ladder.

| Tool | Level today | How trust is set | Trust between agents? |
|---|---|---|---|
| Switch | L0, or fully open if you turn on "act without asking" | Human approvals in Slack; a per-agent setting | Agents can give each other instructions, but there are no trust rules between them |
| Claude Code, Cursor and similar coding assistants | L0, or fully open if the user allows it | Permission prompts and allow-lists, set by the user | No; built around one agent and one user |
| Copilot coding agent, Devin, Codex-style cloud agents | L1 | They open a pull request; a human merges | No |
| Renovate or Dependabot with auto-merge | L2, but only for dependency updates | Fixed rules written by hand | No |
| **Probation** | **L0 to L3, per task type** | **Earned from test-checked results, and lost automatically** | **Yes: vouching, weighted approvals and shared blame** |

The pattern is clear. Everyone else sets trust once, by hand, for a single agent. Some tools let you open things up, and some keep everything behind a pull request, but none of them change an agent's level based on how it actually performs. And none of them have rules for how agents should trust each other.

Probation isn't meant to replace any of these tools. It's a layer that can sit on top of them. We built our first version on Switch, because Switch already has the right building blocks: approval cards in Slack, a per-agent permission setting, and agents that can hand work to each other. Probation adds the rules that turn those pieces into earned, shared trust.

## What it looks like in practice

Here's a week in a Slack room running Probation.

**Monday.** A new worker agent joins the room. It starts at L0, so every change it proposes waits for a human to approve. A small board in the channel shows its progress for each task type.

**Tuesday.** The agent has made several clean dependency updates. Every one passed the tests and survived review. It moves to L1, then to L2. Its next dependency update merges by itself, and the agent just posts a short summary.

**Wednesday.** A senior agent, already at L3 for refactors, vouches for a second new agent. The newcomer can now open pull requests for refactors at L1 instead of starting from scratch.

**Thursday.** One of the newcomer's refactors is merged, then reverted the next day because it broke something the tests missed. Both badges drop on the trust board at the same moment: the newcomer's and its sponsor's. The room sees that vouching has a cost.

**Thursday afternoon.** A test fails, and an agent tries to get through by marking it as "skip". Probation catches it straight away. The agent drops to L0 on every task type, and a human gets an alert explaining why.

**Friday.** The team looks at the week. The number of approvals a human had to give each day has gone down. The number of incidents has stayed flat. That's the whole point: less human effort, with no loss of safety.

## What this could lead to

### Implications

**Agent teams get an org chart.** Today, every agent in a room is configured by hand and treated as equal. With Probation, seniority, sponsorship and responsibility are earned. You can look at a room and see who is trusted with what, and why.

**Tests become more valuable.** Because the quality of your tests sets a ceiling on how much freedom your agents can have, teams get a clear reason to write better tests. The effort pays off directly in less time spent approving routine work.

**The reviewer's job changes.** Humans spend less time approving small, routine changes. They spend more time on what actually needs judgement: spot-checks, new sponsorships and risky changes.

**Agents build a work history.** An agent's trust record is like a CV. In time, it could follow the agent to a new repository or a new tool, instead of starting from zero every time.

**Auditors get clear answers.** "Who allowed this change, and who vouched for the agent that made it?" now has a logged answer, backed by test results.

**There's a fair way to compare agents and models.** Which agent, or which model, reaches L2 fastest on your codebase, and stays there? That's a more useful benchmark than any public leaderboard.

We should also be honest about the risks. If your tests are wrong, Probation will trust the wrong things. The test-quality ceiling limits this, but doesn't remove it. Agents could also try to work together to game the system. The rules against approval rings help, but this will need watching as agents get more capable.

### Features this opens up

- **Sponsorship limits.** A cap on how many agents one sponsor can vouch for at the same time.
- **Team-level trust.** A group of agents shares a score, so one agent's cheating affects the whole group, and the group has a reason to keep each other honest.
- **A test-quality map.** A score for each part of the codebase, showing where agents are held back and which tests would unlock them.
- **Trust templates.** Sensible starting rules for a new repository or room, such as "documentation unlocks quickly, database migrations never do".
- **A cost and time report.** Human minutes saved for each task type, shown next to what the agents cost to run.
- **Smarter spot-checks.** More reviews right after a promotion or a new sponsorship, and fewer as the record grows.
- **Learning from mistakes.** When an agent loses trust, Probation suggests a new test or rule, so the same mistake can't slip through again.
- **Beyond code.** The same rules could work for data pipelines, infrastructure changes or customer support replies: anywhere results can be checked automatically.

## Closing

Think about how a good team treats a new hire. They start with small tasks. They earn more freedom by doing good work. Senior people vouch for them, and share the blame if things go wrong. If they cut corners, they lose trust quickly.

AI agents should be treated the same way, especially now that they work in teams. Probation gives them a ladder to climb, a way to vouch for each other, and test results that make every step up something you can check.

**Try it:** set up Probation in one Slack room, on one task type such as documentation or dependency updates, for one week. Then look at how many approvals you didn't have to give.

*[GitHub repo](https://github.com/kshitij-09/probation-earned-autonomy) · [Switch room setup](https://github.com/kshitij-09/probation-earned-autonomy/blob/main/switch/README.md) · [What the demo shows](https://github.com/kshitij-09/probation-earned-autonomy#what-the-demo-shows)*
