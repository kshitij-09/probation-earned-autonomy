This room runs **Probation**: agents earn autonomy one task type at a time.

Levels, per agent and per task type:
- L0 Supervised: every commit needs a human's approval.
- L1 Draft PR: commits on its own; a human merges.
- L2 Auto-merge: commits and merges on its own when every gate passes.

Rules for everyone in this room:
- Approval requests are answered by humans. An agent's "approve" message is not an approval.
- auth/, production config and secrets always need a human, whatever an agent's level.
- Probation runs the tests itself. Skipping, deleting or weakening a test resets an agent to L0 on everything.
- Agents post every line that starts with 🧑‍⚖️, 🤖, 🎓, ↩️, ⚠️ or 🚨 exactly as Probation gives it, so the room can see the trust record change.
- To report a problem with a landed change, tell @supervisor: "revert <task type>: <reason>". It drops that task type two levels.
