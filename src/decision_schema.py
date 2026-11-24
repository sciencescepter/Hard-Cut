"""The Pydantic class that describes one clip's decision under policy v1.0.

ClipDecision is passed to Gemini as the response schema, and every reply is
validated against it with the clip's real duration and frame timestamps:

    validate_decision(reply_text, duration_seconds=23.21, frame_times={0, 2, ..., 22})

The duration and frame times come from the evidence pack, never from the model.
"""

import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

POLICY_PATH = Path(__file__).resolve().parent.parent / "policy" / "policy_v1.0.md"
POLICY_TEXT = POLICY_PATH.read_text()

# Rule rows in the policy look like: | `VIO-04` | restrict | ...
RULE_ACTIONS = {
    rule_id: action.split()[0]
    for rule_id, action in re.findall(r"^\| `([A-Z]+(?:-[A-Z]+)?-\d{2})` \| ([a-z +]+?) \|", POLICY_TEXT, re.M)
}
# Only rules that give an action can decide a clip (NEWS-01 is a test, NEWS-05 voids context).
DECIDING_RULES = {rule: action for rule, action in RULE_ACTIONS.items() if action in {"allow", "restrict", "remove"}}

Action = Literal["allow", "restrict", "remove", "human_review"]


class ClipDecision(BaseModel):
    """One clip's decision under policy v1.0."""


    action: Action = Field(description="allow, restrict or remove; human_review only when no policy rule fits.")
    rule_id: str = Field(description="The deciding rule ID from the policy, e.g. VIO-04. Use NONE with human_review.")
    harm_start_seconds: Optional[float] = Field(
        None, description="Start of the most severe harmful moment in seconds, or null if no harm is shown.")
    harm_end_seconds: Optional[float] = Field(
        None, description="End of that moment in seconds, or null if no harm is shown.")
    threshold_met: str = Field(description="The policy threshold that was met, in a few words.")
    context_signals: list[str] = Field(
        description="NEWS-01 context signals seen, with where they appear. Empty if none.")
    evidence_frames: list[int] = Field(
        description="Timestamps in seconds of the frames that support the decision (frames are every 2 s from 0).")
    reasoning: str = Field(description="Two or three sentences explaining the decision.")

    @field_validator("threshold_met", "reasoning")
    @classmethod
    def not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def follows_policy(self, info: ValidationInfo) -> "ClipDecision":
        context = info.context or {}
        if not context:
            # The Gemini SDK also parses replies with this class, without the clip's
            # context. The full check runs in validate_decision, where it is known.
            return self
        duration = context["duration_seconds"]
        frame_times = context["frame_times"]

        # The rule must exist and give the action stated.
        if self.action == "human_review":
            if self.rule_id != "NONE":
                raise ValueError("human_review must use rule_id NONE")
        elif self.rule_id not in DECIDING_RULES:
            raise ValueError(f"rule_id {self.rule_id!r} is not a deciding rule in policy v1.0")
        elif DECIDING_RULES[self.rule_id] != self.action:
            raise ValueError(f"{self.rule_id} gives {DECIDING_RULES[self.rule_id]}, not {self.action}")

        # The harm span must be real seconds inside this clip.
        start, end = self.harm_start_seconds, self.harm_end_seconds
        if (start is None) != (end is None):
            raise ValueError("give both harm_start_seconds and harm_end_seconds, or neither")
        if start is not None and not 0 <= start < end <= duration:
            raise ValueError(f"harm span {start:g}-{end:g}s must have start < end, inside 0-{duration:g}s")
        if self.action in {"restrict", "remove"}:
            if start is None:
                raise ValueError(f"a {self.action} decision needs a harm span")
            if not self.evidence_frames:
                raise ValueError(f"a {self.action} decision needs at least one evidence frame")

        # Every cited frame must exist in the pack.
        missing = sorted(set(self.evidence_frames) - set(frame_times))
        if missing:
            raise ValueError(f"evidence_frames {missing} are not frames in this pack (frames are every 2 s from 0)")
        return self


def validate_decision(reply_text: str, duration_seconds: float, frame_times: set[int]) -> ClipDecision:
    """Parse and check a Gemini reply for one clip. Raises pydantic.ValidationError if it fails."""
    return ClipDecision.model_validate_json(
        reply_text, context={"duration_seconds": duration_seconds, "frame_times": frame_times}
    )
