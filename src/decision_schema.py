"""The Pydantic classes that describe one clip's decision under policy v1.0.

ClipDecision is passed to Gemini as the response schema. It holds the decision
and a list of findings. Every reply is validated against it with the clip's real
duration, frames and transcript, which come from the evidence pack and never
from the model.
"""

import re
from pathlib import Path
from typing import Literal, Optional

from langsmith import traceable
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
# The policy says these only apply when the NEWS-01 test is met, so NEWS-01 must be cited too.
NEEDS_NEWS_01 = {"NEWS-02", "NEWS-03", "NEWS-04"}
SEVERITY = {"allow": 0, "restrict": 1, "remove": 2}
EVIDENCE_MARGIN_SECONDS = 2  # frames are 2 s apart, so the nearest one can sit just outside a short harm window

Action = Literal["allow", "restrict", "remove", "human_review"]


class Finding(BaseModel):
    """One rule, where in the clip it applies, why, and the evidence for it."""

    rule_id: str = Field(description="A rule ID from the policy, e.g. VIO-02 or NEWS-01.")
    harm_start_seconds: int = Field(description="First whole second where this finding applies.")
    harm_end_seconds: int = Field(description="Whole second where it ends. Later than the start.")
    rationale: str = Field(description="One or two plain sentences: what is seen or heard and why the rule applies.")
    evidence_frame: Optional[int] = Field(
        None, description="Timestamp in seconds of the frame that triggered this finding, or null.")
    evidence_transcript_line: Optional[int] = Field(
        None, description="Number of the transcript line that triggered this finding, or null.")

    @field_validator("rationale")
    @classmethod
    def not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value


class ClipDecision(BaseModel):
    """One clip's decision under policy v1.0, with the findings behind it."""

    action: Action = Field(description="allow, restrict or remove; human_review only when no policy rule fits.")
    rule_id: str = Field(description="The deciding rule ID from the policy, e.g. VIO-04. Use NONE with human_review.")
    threshold_met: str = Field(description="The policy threshold that was met, in a few words.")
    context_signals: list[str] = Field(
        description="NEWS-01 context signals seen, with where they appear. Empty if none.")
    findings: list[Finding] = Field(
        description="Every rule that applies, with the deciding rule among them. Empty only if no harm is shown at all.")
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

        # The rule must exist and give the action stated.
        if self.action == "human_review":
            if self.rule_id != "NONE":
                raise ValueError("human_review must use rule_id NONE")
        elif self.rule_id not in DECIDING_RULES:
            raise ValueError(f"rule_id {self.rule_id!r} is not a deciding rule in policy v1.0")
        elif DECIDING_RULES[self.rule_id] != self.action:
            raise ValueError(f"{self.rule_id} gives {DECIDING_RULES[self.rule_id]}, not {self.action}")

        for number, finding in enumerate(self.findings, start=1):
            check_finding(f"finding {number} ({finding.rule_id})", finding, self.action, context)

        # The findings must back up the decision.
        cited = {finding.rule_id for finding in self.findings}
        if self.action in {"restrict", "remove"} and self.rule_id not in cited:
            raise ValueError(f"a {self.action} decision needs a finding that cites its deciding rule {self.rule_id}")
        if self.findings and self.action == "allow" and self.rule_id not in cited:
            raise ValueError(f"the findings must include the deciding rule {self.rule_id}")
        if self.rule_id in NEEDS_NEWS_01 and "NEWS-01" not in cited:
            raise ValueError(f"{self.rule_id} relies on NEWS-01, so a finding must cite NEWS-01")
        return self


def check_finding(name: str, finding: Finding, action: str, context: dict) -> None:
    """Raise ValueError if a finding isn't real for this clip or contradicts the decision."""
    duration, frame_times = context["duration_seconds"], context["frame_times"]
    lines = context["transcript_lines"]  # list of (start, end); line numbers start at 1

    if finding.rule_id not in RULE_ACTIONS:
        raise ValueError(f"{name}: rule_id is not in policy v1.0")
    rule_action = RULE_ACTIONS[finding.rule_id]
    if action in SEVERITY and SEVERITY.get(rule_action, 0) > SEVERITY[action]:
        raise ValueError(f"{name}: this rule gives {rule_action}, which is stricter than the decision {action}")

    start, end = finding.harm_start_seconds, finding.harm_end_seconds
    if not 0 <= start < end <= duration:
        raise ValueError(f"{name}: harm window {start}-{end}s must have start < end, inside 0-{duration:g}s")

    frame, line = finding.evidence_frame, finding.evidence_transcript_line
    if (frame is None) == (line is None):
        raise ValueError(f"{name}: give exactly one of evidence_frame or evidence_transcript_line")
    if frame is not None:
        if frame not in frame_times:
            raise ValueError(f"{name}: evidence_frame {frame} is not a frame in this pack (frames are every 2 s from 0)")
        evidence_start = evidence_end = frame
    else:
        if not 1 <= line <= len(lines):
            raise ValueError(f"{name}: transcript line {line} does not exist (there are {len(lines)} lines)")
        evidence_start, evidence_end = lines[line - 1]
    if evidence_start > end + EVIDENCE_MARGIN_SECONDS or evidence_end < start - EVIDENCE_MARGIN_SECONDS:
        raise ValueError(f"{name}: the evidence at {evidence_start:g}-{evidence_end:g}s is outside its "
                         f"harm window {start}-{end}s")


@traceable(name="pydantic_check")
def validate_decision(reply_text: str, duration_seconds: float, frame_times: set[int],
                      transcript_lines: list[tuple[float, float]] = ()) -> ClipDecision:
    """Parse and check a Gemini reply for one clip. Raises pydantic.ValidationError if it fails."""
    return ClipDecision.model_validate_json(reply_text, context={
        "duration_seconds": duration_seconds, "frame_times": frame_times, "transcript_lines": list(transcript_lines)})


def deciding_finding(decision: dict) -> dict | None:
    """The finding that cites the deciding rule (the first one, if there are several)."""
    return next((f for f in decision.get("findings", []) if f["rule_id"] == decision["rule_id"]), None)
