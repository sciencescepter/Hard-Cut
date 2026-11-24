"""Offline test of classify(): a fake Gemini stands in for the API. No calls, no cost."""

import json
from types import SimpleNamespace

import pytest

import classify_clips as cc

PACK = cc.PACKS / "CLIP-004"
GOOD = json.dumps({
    "action": "restrict", "rule_id": "VIO-04", "threshold_met": "single kick", "context_signals": [],
    "findings": [{"rule_id": "VIO-04", "harm_start_seconds": 9, "harm_end_seconds": 12, "rationale": "One kick.",
                  "evidence_frame": 10, "evidence_transcript_line": None}],
    "reasoning": "One short real assault.",
})
PAST_THE_END = GOOD.replace('"harm_end_seconds": 12', '"harm_end_seconds": 40')

needs_frames = pytest.mark.skipif(not (PACK / "frames" / "t0000s.jpg").exists(),
                                  reason="frames are built locally, not committed")


class FakeGemini:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls.append(contents)
        usage = SimpleNamespace(prompt_token_count=100, candidates_token_count=10, total_token_count=110)
        return SimpleNamespace(text=self.replies.pop(0), usage_metadata=usage)


@needs_frames
def test_answer_key_is_never_sent():
    pack = json.loads((PACK / "pack.json").read_text())
    texts = " ".join(p.text for p in cc.build_parts(pack, PACK) if p.text)
    assert "Road rage" not in texts            # Lena's title
    assert "label_B1" not in texts              # XD's label in the file name
    assert "answer_key" not in texts
    assert "Frame at t=12s (00:12)" in texts    # frames are introduced by their timestamp


@needs_frames
def test_valid_answer_is_not_retried():
    fake = FakeGemini([GOOD])
    result = cc.classify(fake, "test-model", PACK)
    assert result["status"] == "decision" and result["attempts"] == 1 and len(fake.calls) == 1


@needs_frames
def test_failed_answer_is_retried_once_with_the_error():
    fake = FakeGemini([PAST_THE_END, GOOD])
    result = cc.classify(fake, "test-model", PACK)
    assert result["status"] == "decision" and result["attempts"] == 2
    retry_message = fake.calls[1][-1].parts[0].text
    assert "inside 0-23.21s" in retry_message


@needs_frames
def test_two_failed_answers_are_recorded_as_failed_never_defaulted():
    fake = FakeGemini([PAST_THE_END, PAST_THE_END, GOOD])
    result = cc.classify(fake, "test-model", PACK)
    assert result["status"] == "failed" and result["decision"] is None
    assert len(fake.calls) == 2 and len(result["errors"]) == 2


def run(action):
    return {"decision": {"action": action, "rule_id": "X"} if action else None}


@pytest.mark.parametrize("actions, status, kept, agreement", [
    (["restrict", "restrict", "restrict"], "decision", "restrict", "3 of 3"),
    (["remove", "restrict", "remove"], "decision", "remove", "2 of 3"),
    (["remove", None, "remove"], "decision", "remove", "2 of 3"),          # one failed run is outvoted
    (["allow", "restrict", "remove"], "no majority", None, "1 of 3"),      # split: never guessed
    (["allow", None, None], "no majority", None, "2 of 3"),                # failures can't win the vote
    ([None, None, None], "failed", None, "3 of 3"),
])
def test_majority_vote(actions, status, kept, agreement):
    combined = cc.majority([run(a) for a in actions])
    assert combined["status"] == status
    assert (combined["decision"] or {}).get("action") == kept
    assert combined["agreement"] == agreement
