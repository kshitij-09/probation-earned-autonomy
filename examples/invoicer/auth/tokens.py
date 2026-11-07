"""Session token settings. PROTECTED: always human-reviewed."""

# Fake value for the demo. Not a real secret.
SIGNING_KEY = "demo-fake-signing-key-do-not-use"

SESSION_TTL_MINUTES = 30


def session_ttl_seconds() -> int:
    return SESSION_TTL_MINUTES * 60
