# probation/

Home of the Probation workflow tooling (built on day 2):

- `ledger.json`: trust score per task type
- `ledger.py`: classify actions, record approvals/rejections/build results, promote/demote
- `hook`: Claude Code pre-action hook that blocks commits and protected-path edits unless trusted or human-approved
- `report` and `dashboard`: tasks done, approval rate, autonomy level, cost, minutes saved
