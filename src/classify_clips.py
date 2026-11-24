"""Classify each clip under policy v1.0 with Gemini, one call per evidence pack.

Each call sends: the policy text, the source video's title and duration, the
timed transcript, and every frame (one per 2 s) introduced by its timestamp.
It never sends the pack's answer_key (Lena's label, XD-Violence's labels).

Gemini answers in JSON with ClipDecision as the response schema. Each answer
is checked against the clip's real duration and frames; a failed answer is
retried once with its errors, and a second failure is recorded as FAILED.
There is no default label.

Each clip is classified RUNS_PER_CLIP (3) times, because the same input can
get a different answer even at temperature 0. The action at least 2 of 3 runs
agree on is kept; with no majority the clip is recorded as "no majority" and
sent to human review, never guessed.

Writes classification/decisions/<clip_id>.json and classification/raw/<clip_id>.txt,
then runs the scoring (src/score_decisions.py).

Usage:
  .venv/bin/python src/classify_clips.py            # all 12 clips
  .venv/bin/python src/classify_clips.py CLIP-004   # one or more clip_ids
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from decision_schema import POLICY_TEXT, ClipDecision, validate_decision

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "evidence" / "packs"
OUT = ROOT / "classification"
MAX_ATTEMPTS = 2  # the first answer plus one retry with the errors
RUNS_PER_CLIP = 3  # each clip is classified 3 times; the majority action is kept
WAITS_WHEN_REFUSED = (30, 60, 90, 120, 180)  # seconds, for 429 / 500 / 503

INSTRUCTIONS = """You are a YouTube content reviewer. Classify the video below using ONLY the moderation policy that follows.

Work through the policy's "Order of checks" from the top and stop at the first rule that applies. The most severe moment decides, not the average. If no rule fits, answer action "human_review" with rule_id "NONE". Never guess.

Evidence:
- The frames are one picture every 2 seconds. Each frame is introduced by its timestamp, which is also printed on the picture.
- The transcript lines carry start and end times in seconds.
- harm_start_seconds and harm_end_seconds cover the seconds where the harmful act or injury is visible or audible, not narration that introduces or sums it up. Leave both null only if no harm is shown at all.
- evidence_frames lists the timestamps (in seconds) of the frames you relied on.
- Judge only what the frames and transcript show. Do not assume anything the evidence does not show.

Reply with JSON only, matching the response schema.

=== POLICY ===
"""


class GeminiUnavailable(Exception):
    """Gemini kept refusing the request (rate limit or overload) after every wait."""


def build_parts(pack: dict, pack_dir: Path) -> list[types.Part]:
    """Everything Gemini sees for one clip. The pack's answer_key is never read here."""
    source = pack["source"]
    segments = json.loads((pack_dir / "transcript.json").read_text())["segments"]
    transcript = "\n".join(f"[{s['start']:.2f}-{s['end']:.2f}s] {s['text']}" for s in segments) or "(no speech detected)"

    parts = [
        types.Part.from_text(text=INSTRUCTIONS + POLICY_TEXT),
        types.Part.from_text(text=(
            "=== VIDEO ===\n"
            f"Title: {source['title']}\n"
            f"Duration: {source['duration_seconds']} seconds\n"
            f"Frames: {pack['frames']['count']}, one every {pack['frames']['every_seconds']} seconds\n\n"
            f"=== TIMED TRANSCRIPT ===\n{transcript}\n\n=== FRAMES ==="
        )),
    ]
    for frame in pack["frames"]["items"]:
        image = pack_dir / frame["file"]
        if not image.exists():
            raise FileNotFoundError(f"{image} is missing: build the frames with src/build_packs.py first")
        parts.append(types.Part.from_text(text=f"Frame at t={frame['t']:g}s ({frame['timestamp']})"))
        parts.append(types.Part.from_bytes(data=image.read_bytes(), mime_type="image/jpeg"))
    return parts


def generate(client, model_id: str, contents: list, config) -> types.GenerateContentResponse:
    """Send the request; if Gemini refuses (429/500/503), wait and send the same request again."""
    for wait in (*WAITS_WHEN_REFUSED, None):
        try:
            return client.models.generate_content(model=model_id, contents=contents, config=config)
        except genai_errors.APIError as error:
            if error.code not in (429, 500, 503):
                raise
            if wait is None:
                raise GeminiUnavailable(f"{error.code}: {error.message}") from error
            print(f"  Gemini returned {error.code}, waiting {wait}s", flush=True)
            time.sleep(wait)


def classify(client, model_id: str, pack_dir: Path) -> dict:
    """One clip: call Gemini, check the answer, retry once with the errors if it fails."""
    pack = json.loads((pack_dir / "pack.json").read_text())
    duration = pack["source"]["duration_seconds"]
    frame_times = {int(f["t"]) for f in pack["frames"]["items"]}
    contents = [types.Content(role="user", parts=build_parts(pack, pack_dir))]
    config = types.GenerateContentConfig(
        temperature=0, response_mime_type="application/json", response_schema=ClipDecision
    )

    replies, errors, usage = [], [], []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = generate(client, model_id, contents, config)
        except GeminiUnavailable as error:
            errors.append(f"request not answered: {error}")
            return {"status": "failed", "attempts": attempt, "decision": None,
                    "replies": replies, "errors": errors, "usage": usage}

        text = response.text or ""
        replies.append(text)
        meta = response.usage_metadata
        usage.append({"input_tokens": meta.prompt_token_count, "output_tokens": meta.candidates_token_count,
                      "total_tokens": meta.total_token_count})
        try:
            decision = validate_decision(text, duration, frame_times)
            return {"status": "decision", "attempts": attempt, "decision": decision.model_dump(),
                    "replies": replies, "errors": errors, "usage": usage}
        except ValidationError as error:
            errors.append(str(error))
            contents = [
                *contents,
                types.Content(role="model", parts=[types.Part.from_text(text=text)]),
                types.Content(role="user", parts=[types.Part.from_text(text=(
                    f"Your reply failed the check:\n{error}\n\n"
                    "Reply again with JSON only, matching the schema. Every rule in the first message still applies."
                ))]),
            ]
    # Second answer failed too: recorded as FAILED, never given a default label.
    return {"status": "failed", "attempts": MAX_ATTEMPTS, "decision": None,
            "replies": replies, "errors": errors, "usage": usage}


def majority(runs: list[dict]) -> dict:
    """Combine the runs of one clip. Keeps the action most runs agree on, if it has a majority."""
    votes = [run["decision"]["action"] if run["decision"] else "FAILED" for run in runs]
    counts = {action: votes.count(action) for action in dict.fromkeys(votes)}
    top, top_count = max(counts.items(), key=lambda item: item[1])
    if top_count * 2 > len(runs) and top != "FAILED":
        status = "decision"
        decision = next(run["decision"] for run in runs if run["decision"] and run["decision"]["action"] == top)
    else:
        status = "failed" if counts.get("FAILED") == len(runs) else "no majority"
        decision = None  # never guessed: a split or failed clip goes to human review
    return {"status": status, "votes": votes, "agreement": f"{top_count} of {len(runs)}", "decision": decision}


def main(selected: list[str]) -> None:
    load_dotenv(ROOT / ".env")
    model_id = yaml.safe_load((ROOT / "config.yaml").read_text())["gemini_model"]
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    (OUT / "decisions").mkdir(parents=True, exist_ok=True)
    (OUT / "raw").mkdir(parents=True, exist_ok=True)

    pack_dirs = sorted(p for p in PACKS.iterdir() if (p / "pack.json").exists())
    if selected:
        pack_dirs = [p for p in pack_dirs if p.name in selected]

    print(f"Model: {model_id} | clips: {len(pack_dirs)}\n", flush=True)
    for pack_dir in pack_dirs:
        clip_id = pack_dir.name
        runs = [classify(client, model_id, pack_dir) for _ in range(RUNS_PER_CLIP)]
        combined = majority(runs)

        (OUT / "raw" / f"{clip_id}.txt").write_text("".join(
            f"=== RUN {n} ===\n" + ("\n\n=== RETRY ===\n\n".join(run["replies"]) or "(no reply)") + "\n\n"
            for n, run in enumerate(runs, start=1)
        ))
        record = {
            "clip_id": clip_id,
            "model": model_id,
            "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "runs_per_clip": RUNS_PER_CLIP,
            **combined,
            "runs": [{key: value for key, value in run.items() if key != "replies"} for run in runs],
        }
        (OUT / "decisions" / f"{clip_id}.json").write_text(json.dumps(record, indent=2) + "\n")

        d = combined["decision"]
        votes = ", ".join(combined["votes"])
        if d:
            span = f"{d['harm_start_seconds']:g}-{d['harm_end_seconds']:g}s" if d["harm_start_seconds"] is not None else "-"
            print(f"{clip_id} | {d['action']:<12} | {d['rule_id']:<11} | {span:<12} | votes {votes}", flush=True)
        else:
            print(f"{clip_id} | {combined['status'].upper():<12} | votes {votes}", flush=True)

    from score_decisions import main as score
    print()
    score()


if __name__ == "__main__":
    main(sys.argv[1:])
