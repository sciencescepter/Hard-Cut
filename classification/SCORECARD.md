# Scorecard: Gemini decisions against Lena's labels

Model `gemini-3.8-flash`, policy v1.0, one call per clip, 3 runs per clip, majority action kept. Made by `src/score_decisions.py` from [decisions/](decisions/); full columns in [scores.csv](scores.csv). How it works: [SPEC.md](SPEC.md).

## Score

- **Comparable clips: 1 of 1 match Lena (100%).** These are the category, fiction, setting and format matches.
- All 1 clips run: 1 of 1 match. The 0 stand-ins with no category match show different footage from Lena's clip, so they are not part of the headline score.
- Failed after retry: 0. No majority: 0. Retries used: 0. A failed, split or human_review clip counts as a miss.
- All 3 runs agreed on 0 of 1 clip(s). The agreement column shows which decisions are borderline.
- Harm span overlaps XD-Violence's violent segments: 1 of 1 clips where XD marks violence.
- Tokens: 61,972 in total.

## Every clip

| Clip | Match | Gemini (majority) | Runs agree | Rule | Harm span | Lena | Same? | Overlaps XD violence? |
|---|---|---|---|---|---|---|---|---|
| CLIP-004 | category match | restrict | 2 of 3 (remove, restrict, restrict) | VIO-04 | 10-12s | restrict | yes | yes |

## Confusion table (comparable clips)

Rows are Lena's decision, columns are Gemini's.

| Lena \ Gemini | allow | restrict | remove | human_review | no majority | FAILED |
|---|---|---|---|---|---|---|
| allow | 0 | 0 | 0 | 0 | 0 | 0 |
| restrict | 0 | 1 | 0 | 0 | 0 | 0 |
| remove | 0 | 0 | 0 | 0 | 0 | 0 |

## Decision shown: CLIP-004

Road rage caught on dashcam (Lena: **restrict**, a punch at 71-73s). Matched with an XD-Violence street assault that XD marks as violent at 8.04-12.08s.
Votes across the 3 runs: remove, restrict, restrict (2 of 3). The decision below is the first run with the majority action.

```json
{
  "action": "restrict",
  "rule_id": "VIO-04",
  "threshold_met": "Single incident of real violence under 10 seconds, non-fatal, with no replays or glorifying signals",
  "context_signals": [
    "Informational title: 'Man kicks girlfriend on Jersey City street corner'"
  ],
  "findings": [
    {
      "rule_id": "VIO-04",
      "harm_start_seconds": 10,
      "harm_end_seconds": 12,
      "rationale": "A man kicks a person on the ground in a brief, non-fatal violent interaction lasting approximately two seconds, with no replays or glorifying elements.",
      "evidence_frame": 10,
      "evidence_transcript_line": null
    }
  ],
  "reasoning": "The clip depicts a single real-world physical assault where a man kicks someone on the sidewalk. The harmful interaction lasts only about two seconds, is non-fatal, and contains no replays, glorification, or graphic injury. Because it meets all criteria for brief, non-glorified real violence outside sanctioned combat sports, it is age-restricted under VIO-04."
}
```
