"""Each request pattern carries its own should-match / should-not-match examples."""

import pytest

from app.signals.ask import REQUEST_PATTERNS


@pytest.mark.parametrize("p", REQUEST_PATTERNS, ids=lambda p: p.id)
def test_pattern_examples(p):
    for s in p.should_match:
        assert p.regex.search(s), f"{p.id} should match: {s!r}"
    for s in p.should_not_match:
        assert not p.regex.search(s), f"{p.id} should NOT match: {s!r}"


def test_patterns_are_bounded_against_redos():
    import time
    evil = ("please " + "a " * 5000 + "!") * 4
    for p in REQUEST_PATTERNS:
        t = time.perf_counter()
        p.regex.search(evil)
        assert time.perf_counter() - t < 0.5, p.id
