"""Probation: earned autonomy for coding agents.

An agent starts at L0 for every task type and climbs the ladder by making
clean, test-checked changes. It loses trust automatically when it slips.
"""

__version__ = "0.1.0"

LEVELS = {
    0: "L0 Supervised: every commit needs a human",
    1: "L1 Draft PR: commits on its own, a human merges",
    2: "L2 Auto-merge: commits and merges on its own when every gate passes",
    3: "L3 Audited: autonomous with random spot-checks (roadmap)",
}
