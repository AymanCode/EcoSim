"""Bounded websocket waits shared by the server tests.

``until`` has two bounds: one wall-clock deadline for the whole call and a
message-count limit, so a missing reply fails the test instead of hanging it,
even while unrelated messages keep arriving.
"""

import signal


def until(ws, predicate, limit=2000, seconds=30):
    """Return the first message matching *predicate*; fail after *seconds* in total or *limit* messages."""

    def _timeout(signum, frame):
        raise TimeoutError(f"no matching websocket message within {seconds} seconds")

    previous_handler = signal.signal(signal.SIGALRM, _timeout)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        for _ in range(limit):
            msg = ws.receive_json()
            if predicate(msg):
                return msg
        raise AssertionError(f"no matching message within {limit} messages")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def setup(ws, config, **kw):
    """Send SETUP with *config* and return the SETUP_COMPLETE or error reply; *kw* goes to ``until``."""
    ws.send_json({"command": "SETUP", "config": config})
    return until(ws, lambda m: m.get("type") == "SETUP_COMPLETE" or "error" in m, **kw)
