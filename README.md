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

Each clip is classified as allow, restrict or remove under policy v1.0 by Gemini (`gemini-3.8-flash`, JSON reply with a Pydantic class as the schema), 3 times with a majority vote, then scored against Lena's label. This stage runs CLIP-004 as the worked example.

- [classification/SPEC.md](classification/SPEC.md): what goes into each call, what each finding must contain and what happens when it fails, and what gets saved.
- [classification/SCORECARD.md](classification/SCORECARD.md): the result for CLIP-004, with the full decision.
- [src/decision_schema.py](src/decision_schema.py), [src/classify_clips.py](src/classify_clips.py), [src/score_decisions.py](src/score_decisions.py), and offline tests in [tests/](tests/).

```bash
.venv/bin/python -m pytest -q                       # offline, no API calls
.venv/bin/python src/classify_clips.py CLIP-004     # needs GEMINI_API_KEY in .env and the frames built
```
