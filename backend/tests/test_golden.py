"""Presentation changes must never change a decision (owner requirement, Phase 2)."""

import json

from tests.golden import PATH, decisions


def test_decisions_identical_to_snapshot():
    assert decisions() == json.loads(PATH.read_text())
