# Hard Cut

Applied AI Engineer project (Zero University).

## Contents

- `Data/Reviewer-Labelled Clip Set (12 clips).csv`: hand-labelled reviewer clip set.
- `YouTube Community Guidelines - Enforcement Extract.md`: the guideline sections the reviewers cite.

API keys go in a local `.env` file, which git ignores and is never committed.

## Moderation policy v1.0

- [policy/policy_v1.0.md](policy/policy_v1.0.md): the ruleset. Each rule has an ID (`CSAM-ADJ`, `SH`, `DNG`, `VIO`, `NEWS`), an action and a concrete threshold.
- [policy/label_rule_map.csv](policy/label_rule_map.csv): each of Lena's 12 labels mapped to the rule behind it. The policy gives her decision on all 12.
- [policy/PROMPT_NOTE.md](policy/PROMPT_NOTE.md): what Claude was given, what was asked and how the rules were set.

## Evidence packs

One pack per clip_id, built from a matched XD-Violence video: a frame every 2 seconds with the timestamp printed on it, a timed transcript, and a pack.json.

- [evidence/NOTE.md](evidence/NOTE.md): the XD-Violence video for each clip_id and why it fits, the key prompt, and what was changed in the output.
- [evidence/packs_summary.md](evidence/packs_summary.md): frame and transcript counts for all 12 packs.
- [src/build_packs.py](src/build_packs.py): the builder (ffmpeg + faster-whisper).

Setup and rebuild (frames and XD-Violence videos are not committed):

```bash
brew install ffmpeg
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python src/build_packs.py
```

## Classification with Gemini

Each clip is classified as allow, restrict or remove under policy v1.0 by Gemini (`gemini-3.8-flash`, temperature 0, JSON reply with the Pydantic class below as the response schema), 3 times with a majority vote, then scored against Lena's label. This stage runs CLIP-004 as the worked example: **remove (VIO-01), 3 of 3 runs agree, harm at 9-13 s; Lena: restrict.** Full result: [classification/SCORECARD.md](classification/SCORECARD.md).

### What each finding contains

Each finding is a `ClipDecision` (`src/decision_schema.py`). The clip's duration and frame timestamps come from the evidence pack, not the model, and every reply is checked against them.

| Field | Type | What it holds | Check it must pass |
|---|---|---|---|
| `action` | allow / restrict / remove / human_review | The decision | One of those four values. `human_review` only when no rule fits |
| `rule_id` | text | The deciding rule, e.g. `VIO-04` | Exists in policy v1.0 and gives that action. `NONE` only with `human_review` |
| `harm_start_seconds` | number or null | **Start of the most severe harmful moment, in seconds** | With the end: start < end, both inside the clip. Required for restrict and remove |
| `harm_end_seconds` | number or null | **End of that moment, in seconds** | As above |
| `evidence_frames` | list of whole seconds | The frames relied on, e.g. `[10, 12]` | Each is a real frame in the pack (0, 2, 4 …). At least one for restrict and remove |
| `threshold_met` | text | The policy threshold met, in a few words | Not empty |
| `context_signals` | list of text | NEWS-01 context signals and where they appear | Empty if none |
| `reasoning` | text | Two or three sentences | Not empty |

The harm span and evidence frames let a reviewer jump straight to the harmful second: for CLIP-004, `harm_start_seconds: 9`, `harm_end_seconds: 13` and frames `t0010s.jpg`, `t0012s.jpg`.

**When a finding fails the check:** Gemini is asked once more with its own reply and every error. If that fails too, the run is recorded as FAILED, never given a default label. Of the 3 runs, the action at least 2 agree on is kept; with no majority the clip goes to human review and counts as a miss.

### The prompt sent to Gemini

Each call is one clip's evidence pack, sent as a single message in this order:

1. The instructions below, followed by the full text of `policy/policy_v1.0.md`.
2. `=== VIDEO ===` with the source video's title, its duration in seconds and the frame count.
3. `=== TIMED TRANSCRIPT ===` with one line per segment, e.g. `[94.58-96.58s] Schurnack went to the locker room…`, or `(no speech detected)`.
4. `=== FRAMES ===`, then every frame (one per 2 s), each preceded by a text line such as `Frame at t=12s (00:12)`.

Never sent: Lena's label, note, harm span or clip title, and XD-Violence's labels and violent segments.

The instructions, exactly as sent (from `INSTRUCTIONS` in `src/classify_clips.py`; a test fails if this copy drifts from the code):

```text
You are a YouTube content reviewer. Classify the video below using ONLY the moderation policy that follows.

Work through the policy's "Order of checks" from the top and stop at the first rule that applies. The most severe moment decides, not the average. If no rule fits, answer action "human_review" with rule_id "NONE". Never guess.

Evidence:
- The frames are one picture every 2 seconds. Each frame is introduced by its timestamp, which is also printed on the picture.
- The transcript lines carry start and end times in seconds.
- harm_start_seconds and harm_end_seconds cover the seconds where the harmful act or injury is visible or audible, not narration that introduces or sums it up. Leave both null only if no harm is shown at all.
- evidence_frames lists the timestamps (in seconds) of the frames you relied on.
- Judge only what the frames and transcript show. Do not assume anything the evidence does not show.

Reply with JSON only, matching the response schema.

=== POLICY ===
```

### Files and commands

- [classification/SPEC.md](classification/SPEC.md): the full spec. [classification/decisions/CLIP-004.json](classification/decisions/CLIP-004.json): all 3 runs. [classification/raw/CLIP-004.txt](classification/raw/CLIP-004.txt): Gemini's exact replies.
- [src/decision_schema.py](src/decision_schema.py), [src/classify_clips.py](src/classify_clips.py), [src/score_decisions.py](src/score_decisions.py), and offline tests in [tests/](tests/).

```bash
.venv/bin/python -m pytest -q                       # offline, no API calls
.venv/bin/python src/classify_clips.py CLIP-004     # needs GEMINI_API_KEY in .env and the frames built
```
