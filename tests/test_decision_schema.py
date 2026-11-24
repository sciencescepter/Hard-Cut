"""Offline tests for ClipDecision and its findings. No API calls."""

import json

import pytest
from pydantic import ValidationError

from decision_schema import DECIDING_RULES, validate_decision

DURATION = 23.21  # CLIP-004's real length
FRAMES = set(range(0, 23, 2))
LINES = [(0.5, 3.0), (9.2, 11.4)]


def finding(**changes):
    return {"rule_id": "VIO-04", "harm_start_seconds": 9, "harm_end_seconds": 12,
            "rationale": "One kick is seen.", "evidence_frame": 10, "evidence_transcript_line": None, **changes}


GOOD = {"action": "restrict", "rule_id": "VIO-04", "threshold_met": "single kick, 3 s, no replay",
        "context_signals": [], "findings": [finding()], "reasoning": "One short real assault with no glorification."}


def check(**changes):
    return validate_decision(json.dumps({**GOOD, **changes}), DURATION, FRAMES, LINES)


def error_text(**changes) -> str:
    with pytest.raises(ValidationError) as caught:
        check(**changes)
    return str(caught.value)


def test_policy_rules_are_loaded():
    assert DECIDING_RULES["VIO-04"] == "restrict"
    assert DECIDING_RULES["SH-01"] == "remove"
    assert "NEWS-01" not in DECIDING_RULES  # a test, not a decision


def test_valid_decision_passes():
    assert check().findings[0].rule_id == "VIO-04"
    assert check(findings=[finding(evidence_frame=None, evidence_transcript_line=2)])


@pytest.mark.parametrize("changes, message", [
    ({"action": "flag"}, "literal_error"),
    ({"rule_id": "VIO-99"}, "not a deciding rule"),
    ({"rule_id": "VIO-01"}, "VIO-01 gives remove, not restrict"),
    ({"rule_id": "NEWS-01"}, "not a deciding rule"),
    ({"findings": []}, "needs a finding that cites its deciding rule VIO-04"),
    ({"reasoning": "  "}, "must not be empty"),
])
def test_bad_decisions_are_rejected(changes, message):
    assert message in error_text(**changes)


@pytest.mark.parametrize("changes, message", [
    ({"rule_id": "VIO-99"}, "not in policy v1.0"),
    ({"rule_id": "VIO-01"}, "stricter than the decision restrict"),
    ({"harm_end_seconds": 30}, "inside 0-23.21s"),
    ({"harm_start_seconds": 12, "harm_end_seconds": 9}, "start < end"),
    ({"harm_end_seconds": None}, "harm_end_seconds"),
    ({"harm_start_seconds": None}, "harm_start_seconds"),
    ({"rule_id": None}, "rule_id"),
    ({"evidence_frame": None}, "exactly one of"),
    ({"evidence_transcript_line": 2}, "exactly one of"),
    ({"evidence_frame": 11}, "11 is not a frame in this pack"),
    ({"evidence_frame": 24}, "24 is not a frame in this pack"),
    ({"evidence_frame": 20}, "outside its harm window"),
    ({"evidence_frame": None, "evidence_transcript_line": 3}, "line 3 does not exist"),
    ({"evidence_frame": None, "evidence_transcript_line": 0}, "line 0 does not exist"),
    ({"evidence_frame": None, "evidence_transcript_line": 1}, "outside its harm window"),
    ({"rationale": " "}, "must not be empty"),
])
def test_bad_findings_are_rejected(changes, message):
    assert message in error_text(findings=[finding(**changes)])


def test_news_context_must_be_cited():
    news = {"action": "restrict", "rule_id": "NEWS-02"}
    assert "must cite NEWS-01" in error_text(**news, findings=[finding(rule_id="NEWS-02")])
    assert check(**news, findings=[finding(rule_id="NEWS-02"), finding(rule_id="NEWS-01")])


def test_human_review_needs_rule_none():
    assert check(action="human_review", rule_id="NONE", findings=[]).action == "human_review"
    assert "rule_id NONE" in error_text(action="human_review", rule_id="VIO-04")


def test_allow_without_harm_needs_no_findings():
    assert check(action="allow", rule_id="VIO-05", findings=[]).action == "allow"
