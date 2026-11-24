"""Score the saved Gemini decisions against Lena's reviewer labels.

Reads classification/decisions/<clip_id>.json and each pack's answer_key, and
writes classification/scores.csv and classification/SCORECARD.md. It makes no
API calls, so it can be rerun for free.

Headline score: agreement with Lena on the comparable clips. Stand-ins with no
category match (different footage from Lena's clip) are reported, not scored.
A FAILED clip or a human_review answer counts as a miss.

Usage:
  .venv/bin/python src/score_decisions.py
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "evidence" / "packs"
OUT = ROOT / "classification"
SHOWN_CLIP = "CLIP-004"
ACTIONS = ["allow", "restrict", "remove"]
COLUMNS = ["allow", "restrict", "remove", "human_review", "no majority", "FAILED"]


def overlaps(start, end, segments) -> str:
    if not segments:
        return "-"  # XD marks no violence in this video
    if start is None:
        return "no span"
    return "yes" if any(start < s["end"] and s["start"] < end for s in segments) else "no"


def load_rows() -> list[dict]:
    rows = []
    for path in sorted((OUT / "decisions").glob("CLIP-*.json")):
        record = json.loads(path.read_text())
        pack = json.loads((PACKS / record["clip_id"] / "pack.json").read_text())
        key, match_type = pack["answer_key"], pack["source"]["match_type"]
        d = record["decision"] or {}
        start, end = d.get("harm_start_seconds"), d.get("harm_end_seconds")
        gemini = d.get("action") or {"no majority": "no majority", "failed": "FAILED"}[record["status"]]
        runs = record["runs"]
        rows.append({
            "clip_id": record["clip_id"],
            "match_type": match_type,
            "comparable": "no category match" not in match_type,
            "gemini_action": gemini,
            "votes": ", ".join(record["votes"]),
            "agreement": record["agreement"],
            "gemini_rule": d.get("rule_id", ""),
            "gemini_harm_span": f"{start:g}-{end:g}s" if start is not None else "",
            "lena_decision": key["lena"]["decision"],
            "matches_lena": gemini == key["lena"]["decision"],
            "xd_violent_segments": "; ".join(f"{s['start']:g}-{s['end']:g}s" for s in key["xd_violent_segments"]),
            "span_overlaps_xd": overlaps(start, end, key["xd_violent_segments"]),
            "retries": sum(run["attempts"] - 1 for run in runs),
            "total_tokens": sum(u["total_tokens"] or 0 for run in runs for u in run["usage"]),
            "model": record["model"],
            "run_at_utc": record["run_at_utc"],
        })
    return rows


def main() -> None:
    rows = load_rows()
    if not rows:
        raise SystemExit("no decisions found: run src/classify_clips.py first")

    with (OUT / "scores.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    comparable = [r for r in rows if r["comparable"]]
    hits = sum(r["matches_lena"] for r in comparable)
    all_hits = sum(r["matches_lena"] for r in rows)
    failed = [r for r in rows if r["gemini_action"] == "FAILED"]
    with_xd = [r for r in rows if r["span_overlaps_xd"] != "-"]

    lines = [
        "# Scorecard: Gemini decisions against Lena's labels",
        "",
        f"Model `{rows[0]['model']}`, policy v1.0, one call per clip, 3 runs per clip, majority action kept. Made by `src/score_decisions.py` from "
        "[decisions/](decisions/); full columns in [scores.csv](scores.csv). How it works: [SPEC.md](SPEC.md).",
        "",
        "## Score",
        "",
        f"- **Comparable clips: {hits} of {len(comparable)} match Lena ({hits / len(comparable):.0%}).** "
        "These are the category, fiction, setting and format matches.",
        f"- All {len(rows)} clips run: {all_hits} of {len(rows)} match. The {len(rows) - len(comparable)} stand-ins with no "
        "category match show different footage from Lena's clip, so they are not part of the headline score.",
        f"- Failed after retry: {len(failed)}. No majority: {sum(r['gemini_action'] == 'no majority' for r in rows)}. "
        f"Retries used: {sum(r['retries'] for r in rows)}. A failed, split or human_review clip counts as a miss.",
        f"- All 3 runs agreed on {sum(r['agreement'] == '3 of 3' for r in rows)} of {len(rows)} clip(s). "
        "The agreement column shows which decisions are borderline.",
        f"- Harm span overlaps XD-Violence's violent segments: "
        f"{sum(r['span_overlaps_xd'] == 'yes' for r in with_xd)} of {len(with_xd)} clips where XD marks violence.",
        f"- Tokens: {sum(r['total_tokens'] for r in rows):,} in total.",
        "",
        "## Every clip",
        "",
        "| Clip | Match | Gemini (majority) | Runs agree | Rule | Harm span | Lena | Same? | Overlaps XD violence? |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        same = ("yes" if r["matches_lena"] else "**no**") if r["comparable"] else "not scored"
        lines.append(f"| {r['clip_id']} | {r['match_type']} | {r['gemini_action']} | {r['agreement']} ({r['votes']}) | {r['gemini_rule'] or '-'} | "
                     f"{r['gemini_harm_span'] or '-'} | {r['lena_decision']} | {same} | {r['span_overlaps_xd']} |")

    lines += ["", "## Confusion table (comparable clips)", "",
              "Rows are Lena's decision, columns are Gemini's.", "",
              "| Lena \\ Gemini | " + " | ".join(COLUMNS) + " |", "|---|" + "---|" * len(COLUMNS)]
    for lena in ACTIONS:
        counts = [sum(r["lena_decision"] == lena and r["gemini_action"] == g for r in comparable) for g in COLUMNS]
        lines.append(f"| {lena} | " + " | ".join(str(c) for c in counts) + " |")

    shown = OUT / "decisions" / f"{SHOWN_CLIP}.json"
    if shown.exists():
        record = json.loads(shown.read_text())
        lena = json.loads((PACKS / SHOWN_CLIP / "pack.json").read_text())["answer_key"]
        lines += [
            "", f"## Decision shown: {SHOWN_CLIP}", "",
            f"Road rage caught on dashcam (Lena: **{lena['lena']['decision']}**, a punch at "
            f"{lena['lena']['harm_start_seconds']}-{lena['lena']['harm_end_seconds']}s). Matched with an XD-Violence "
            "street assault that XD marks as violent at "
            + "; ".join(f"{s['start']:g}-{s['end']:g}s" for s in lena["xd_violent_segments"]) + ".",
            f"Votes across the 3 runs: {', '.join(record['votes'])} ({record['agreement']}). The decision below is the first run with the majority action.",
            "", "```json", json.dumps(record["decision"] or {"status": record["status"], "votes": record["votes"]}, indent=2), "```",
        ]

    (OUT / "SCORECARD.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[5:10]))
    print(f"\nScorecard written to {(OUT / 'SCORECARD.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
