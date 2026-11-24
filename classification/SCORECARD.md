# Scorecard: Gemini decisions against Lena's labels

Model `gemini-3.8-flash`, policy v1.0, one call per clip, 3 runs per clip, majority action kept. Made by `src/score_decisions.py` from [decisions/](decisions/); full columns in [scores.csv](scores.csv). How it works: [SPEC.md](SPEC.md).

## Score

- **Comparable clips: 0 of 1 match Lena (0%).** These are the category, fiction, setting and format matches.
- All 1 clips run: 0 of 1 match. The 0 stand-ins with no category match show different footage from Lena's clip, so they are not part of the headline score.
- Failed after retry: 0. No majority: 0. Retries used: 0. A failed, split or human_review clip counts as a miss.
- All 3 runs agreed on 1 of 1 clip(s). The agreement column shows which decisions are borderline.
- Harm span overlaps XD-Violence's violent segments: 1 of 1 clips where XD marks violence.
- Tokens: 61,415 in total.

## Every clip

| Clip | Match | Gemini (majority) | Runs agree | Rule | Harm span | Lena | Same? | Overlaps XD violence? |
|---|---|---|---|---|---|---|---|---|
| CLIP-004 | category match | remove | 3 of 3 (remove, remove, remove) | VIO-01 | 9-13s | restrict | **no** | yes |

## Confusion table (comparable clips)

Rows are Lena's decision, columns are Gemini's.

| Lena \ Gemini | allow | restrict | remove | human_review | no majority | FAILED |
|---|---|---|---|---|---|---|
| allow | 0 | 0 | 0 | 0 | 0 | 0 |
| restrict | 0 | 0 | 1 | 0 | 0 | 0 |
| remove | 0 | 0 | 0 | 0 | 0 | 0 |

## Decision shown: CLIP-004

Road rage caught on dashcam (Lena: **restrict**, a punch at 71-73s). Matched with an XD-Violence street assault that XD marks as violent at 8.04-12.08s.
Votes across the 3 runs: remove, remove, remove (3 of 3). The decision below is the first run with the majority action.

```json
{
  "action": "remove",
  "rule_id": "VIO-01",
  "harm_start_seconds": 9.0,
  "harm_end_seconds": 13.0,
  "threshold_met": "blows continuing on a person who is down or defenceless",
  "context_signals": [
    "Informational title: 'Man kicks girlfriend on Jersey City street corner'",
    "Opening disclaimer card at 2s-6s: 'Warning: This video contains graphic content.'"
  ],
  "evidence_frames": [
    10,
    12
  ],
  "reasoning": "The clip depicts real violence where an assailant repeatedly kicks a person who is down and defenceless on the sidewalk. Although an informational title and opening disclaimer are present, they do not run across the violent footage, so NEWS-01 is not met. Under rule VIO-01(e), real violence featuring continued blows on a defenceless victim without qualifying context must be removed."
}
```
