"""Offline tests for ClipDecision. No API calls."""

import json

import pytest
from pydantic import ValidationError

from decision_schema import DECIDING_RULES, validate_decision

DURATION = 23.21  # CLIP-004's real length
FRAMES = set(range(0, 23, 2))

GOOD = {
    "action": "restrict", "rule_id": "VIO-04", "harm_start_seconds": 9, "harm_end_seconds": 12,
    "threshold_met": "single kick, 3 s, no replay", "context_signals": [],
    "evidence_frames": [10, 12], "reasoning": "One short real assault with no glorification.",
}


def check(**changes):
    return validate_decision(json.dumps({**GOOD, **changes}), DURATION, FRAMES)


def error_text(**changes) -> str:
    with pytest.raises(ValidationError) as caught:
        check(**changes)
    return str(caught.value)


def test_policy_rules_are_loaded():
    assert DECIDING_RULES["VIO-04"] == "restrict"
    assert DECIDING_RULES["SH-01"] == "remove"
    assert "NEWS-01" not in DECIDING_RULES  # a test, not a decision


def test_valid_decision_passes():
    assert check().rule_id == "VIO-04"


@pytest.mark.parametrize("changes, message", [
    ({"action": "flag"}, "literal_error"),
    ({"rule_id": "VIO-99"}, "not a deciding rule"),
    ({"rule_id": "VIO-01"}, "VIO-01 gives remove, not restrict"),
    ({"rule_id": "NEWS-01"}, "not a deciding rule"),
    ({"harm_end_seconds": 30}, "inside 0-23.21s"),
    ({"harm_start_seconds": 12, "harm_end_seconds": 9}, "start < end"),
    ({"harm_end_seconds": None}, "both harm_start_seconds and harm_end_seconds"),
    ({"harm_start_seconds": None, "harm_end_seconds": None}, "needs a harm span"),
    ({"evidence_frames": []}, "needs at least one evidence frame"),
    ({"evidence_frames": [11]}, "[11] are not frames in this pack"),
    ({"evidence_frames": [24]}, "[24] are not frames in this pack"),
    ({"reasoning": "  "}, "must not be empty"),
])
def test_bad_decisions_are_rejected(changes, message):
    assert message in error_text(**changes)


def test_human_review_needs_rule_none():
    assert check(action="human_review", rule_id="NONE", harm_start_seconds=None,
                 harm_end_seconds=None, evidence_frames=[]).action == "human_review"
    assert "rule_id NONE" in error_text(action="human_review", rule_id="VIO-04")


def test_allow_without_harm_needs_no_span():
    assert check(action="allow", rule_id="VIO-05", harm_start_seconds=None,
                 harm_end_seconds=None, evidence_frames=[]).action == "allow"
