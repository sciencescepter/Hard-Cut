# Classifier spec: policy v1.0 decisions with Gemini

Each clip is classified as `allow`, `restrict` or `remove` under [policy v1.0](../policy/policy_v1.0.md), and the result is scored against Lena's reviewer label.

**This stage runs CLIP-004 only**, as the worked example. The same command runs all 12 (`.venv/bin/python src/classify_clips.py`). Result: [SCORECARD.md](SCORECARD.md).

Code: [src/decision_schema.py](../src/decision_schema.py) (the Pydantic class), [src/classify_clips.py](../src/classify_clips.py) (the Gemini calls), [src/score_decisions.py](../src/score_decisions.py) (the scoring).

## 1. What goes into each Gemini call

**One call per clip_id, built from that clip's evidence pack** (`evidence/packs/<clip_id>/`). One clip per call keeps every frame and transcript line tied to a single decision, so evidence from one clip can never leak into another's.

| Sent to Gemini | Never sent |
|---|---|
| The full text of `policy/policy_v1.0.md` | Lena's decision, harm span, guideline reference and note |
| The source video's own title and its duration in seconds (`pack.json` → `source`) | Lena's clip title (it describes different footage from the stand-in) |
| The timed transcript with exact start and end seconds (`transcript.json`), or "(no speech detected)" | XD-Violence's labels and violent segments (`pack.json` → `answer_key`) |
| Every frame (one per 2 seconds), each introduced by a text line `Frame at t=42s (00:42)`, with the same time printed on the picture | The match type and "why it fits" text |

The model is told to work through the policy's order of checks, stop at the first rule that applies, and answer `human_review` with rule `NONE` when no rule fits, as policy step 7 requires.

Settings: model from `config.yaml` (`gemini-3.8-flash`), temperature 0, `response_mime_type="application/json"`, `response_schema=ClipDecision`.

## 2. What each finding must contain, and what happens when it fails

**Each finding is a `ClipDecision`:**

| Field | Rule it must pass |
|---|---|
| `action` | One of `allow`, `restrict`, `remove`, `human_review` |
| `rule_id` | A deciding rule ID that exists in policy v1.0 and gives that action (e.g. `VIO-04` → `restrict`). `NONE` only with `human_review` |
| `harm_start_seconds`, `harm_end_seconds` | Both or neither. When given: start < end, both inside 0 and the clip's duration. Required for `restrict` and `remove` |
| `evidence_frames` | Timestamps of frames that really exist in the pack (0, 2, 4 …). At least one for `restrict` and `remove` |
| `threshold_met` | The policy threshold that was met, in a few words. Not empty |
| `context_signals` | The NEWS-01 context signals seen, with where they appear. Empty if none |
| `reasoning` | Two or three sentences. Not empty |

The clip's duration and frame timestamps come from the pack, not from the model, and are passed to the check as validation context.

**When an answer fails the check:**
1. The reply is saved exactly as received.
2. Gemini is asked once more, in the same conversation, with its own reply and every validation error attached.
3. If the second answer also fails, the clip is recorded as **FAILED**, with both raw replies and all errors. It is never given a default label, and it counts as a miss in the score.

**Each clip is classified 3 times.** The same input can get a different answer even at temperature 0: CLIP-004 got `restrict` (VIO-04) in an earlier test run and `remove` (VIO-01) in the first run of this script. The action that at least 2 of the 3 runs agree on is kept, along with the first run that gave it. With no majority the clip is recorded as **no majority**, sent to human review and counted as a miss. A failed run can't win the vote.

If Gemini refuses to answer at all (rate limit or overload), the same request is sent again after 30, 60, 90, 120 and 180 seconds. If it still isn't answered, the clip is recorded as FAILED for that reason.

## 3. What the script hands back

**Saved in the repo, under `classification/`:**

| File | Contents |
|---|---|
| `decisions/<clip_id>.json` | The majority decision, the 3 votes and how many agreed, and each run's decision (or FAILED with the errors), attempts and token counts |
| `raw/<clip_id>.txt` | Gemini's replies exactly as received, for all 3 runs, including any retry |
| `scores.csv` | One row per clip: Gemini's majority action, the votes, rule, Lena's decision, match, whether the clip is comparable, harm span and whether it overlaps XD-Violence's violent segments |
| `SCORECARD.md` | The score: matches against Lena, a confusion table, span overlap, failures, tokens, and one full decision shown |

**How it is scored:**
- **Headline:** agreement with Lena on the **8 comparable clips** (category, fiction, setting and format matches). The 4 stand-ins with no category match (CLIP-002, 005, 006, 009) show different footage from Lena's clip, so their decisions are reported but not scored.
- Agreement on all 12 is shown as well, for transparency.
- For clips where XD-Violence marks violence, whether Gemini's harm span overlaps it.

**Decision shown:** CLIP-004 (road rage, dashcam), printed in full in the scorecard. It is a direct category match, and both Lena (a 2 s punch) and XD-Violence (8-12 s) mark a short harm span, so the rule, the span and the threshold can all be checked by eye.
