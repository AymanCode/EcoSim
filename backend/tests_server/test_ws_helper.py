import signal
import time

import pytest

from _ws import until


class _NoisySocket:
    """Fake websocket that keeps sending unrelated messages every 0.02 s."""

    def receive_json(self):
        time.sleep(0.02)
        return {"type": "noise"}


def test_deadline_covers_the_whole_call_not_the_gap_between_messages():
    previous_handler = signal.getsignal(signal.SIGALRM)
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        until(_NoisySocket(), lambda m: False, limit=1000, seconds=0.1)
    assert time.monotonic() - start < 0.5
    assert signal.getsignal(signal.SIGALRM) is previous_handler
