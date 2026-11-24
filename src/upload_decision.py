"""The upload decision script: one clip in, one decision out.

    decide_upload(video, title, is_news_report, pack_dir, ...)

returns a dict with

    decision             allow, restrict or remove. None when routed to a human
    age_restricted       True only with restrict
    findings             rule_id, harm window, rationale and evidence for each
    validation_status    "validated" or "routed_to_human_review"
    routed_reason        why it was routed, in plain words. None when validated
    langsmith_trace_url  the link to the trace. None when tracing is off

The upload page calls this function and nothing else.

Usage:
  .venv/bin/python src/upload_decision.py video.mp4 --title "Evening bulletin" --news
"""

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv
from google import genai
from langsmith import traceable
from langsmith.utils import ContextThreadPoolExecutor

import tracing
from build_packs import WHISPER_MODEL, build_upload_pack, mmss_exact
from classify_clips import ROOT, RUNS_PER_CLIP, classify, majority

VALIDATED = "validated"
ROUTED = "routed_to_human_review"


def hhmmss(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


NEWS_SAFETY_NET = "news_safety_net"


def route(combined: dict, is_news_report: bool) -> tuple[str, str | None, str | None]:
    """(validation_status, why it was routed, the reason in plain words). Anything that isn't a clear, validated label goes to a human."""
    if combined["status"] == "failed":
        return ROUTED, "failed_check", "Every answer failed its check or was not returned, so there is no decision."
    if combined["status"] == "no majority":
        return ROUTED, "no_majority", f"The runs did not agree on one valid answer ({combined['agreement']} at most)."
    if combined["decision"]["action"] == "human_review":
        return ROUTED, "no_rule_fits", "No rule in policy v1.0 fits this clip."
    if is_news_report and combined["decision"]["action"] == "remove":
        # Checked after validation, not inside it: a retry that says "not remove" would push
        # Gemini into a softer label. The answer is kept as it is and a person decides.
        return (ROUTED, NEWS_SAFETY_NET,
                "This upload is marked as a news report, and a news report is never removed automatically.")
    return VALIDATED, None, None


def shown_findings(decision: dict, pack: dict, segments: list[dict]) -> list[dict]:
    """Findings ready to show: the HH:MM:SS window, and the frame or transcript line itself."""
    frames = {int(frame["t"]): frame["file"] for frame in pack["frames"]["items"]}
    shown = []
    for finding in sorted(decision["findings"], key=lambda f: (f["harm_start_seconds"], f["rule_id"])):
        if finding["evidence_frame"] is not None:
            t = finding["evidence_frame"]
            evidence = {"type": "frame", "seconds": t, "time": hhmmss(t), "file": frames[t]}
        else:
            line = segments[finding["evidence_transcript_line"] - 1]
            evidence = {"type": "transcript", "text": line["text"],
                        "time": f"{mmss_exact(line['start'])} to {mmss_exact(line['end'])}"}
        shown.append({
            "rule_id": finding["rule_id"],
            "harm_start_seconds": finding["harm_start_seconds"],
            "harm_end_seconds": finding["harm_end_seconds"],
            "harm_window": f"{hhmmss(finding['harm_start_seconds'])} to {hhmmss(finding['harm_end_seconds'])}",
            "rationale": finding["rationale"],
            "evidence": evidence,
        })
    return shown


@traceable(name="upload_decision", process_inputs=lambda i: {"is_news_report": i["is_news_report"], "model": i["model_id"]})
def decide_pack(client, model_id: str, pack_dir: Path, is_news_report: bool) -> dict:
    """Ask Gemini RUNS_PER_CLIP times, check each answer, take the majority and decide what may be shown."""
    with ContextThreadPoolExecutor(RUNS_PER_CLIP) as pool:
        runs = list(pool.map(lambda _: classify(client, model_id, pack_dir), range(RUNS_PER_CLIP)))
    combined = majority(runs)
    status, cause, reason = route(combined, is_news_report)

    pack = json.loads((pack_dir / "pack.json").read_text())
    segments = json.loads((pack_dir / "transcript.json").read_text())["segments"]
    answer = combined["decision"] if status == VALIDATED else None
    return {
        "decision": answer["action"] if answer else None,
        "age_restricted": bool(answer) and answer["action"] == "restrict",
        "reasoning": answer["reasoning"] if answer else None,
        "findings": shown_findings(answer, pack, segments) if answer else [],
        "validation_status": status,
        "routed_cause": cause,
        "routed_reason": reason,
        "langsmith_trace_url": tracing.current_trace_url(),
        "langsmith_trace_id": tracing.current_trace_id(),
        "agreement": combined["agreement"] if answer else None,
        "is_news_report": is_news_report,
        "model": model_id,
        "decided_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # The answers and errors behind a routed clip stay in the log, never in what the page shows.
        "log": {"votes": combined["votes"], "runs": runs},
    }


def decide_upload(video: Path, title: str, is_news_report: bool, pack_dir: Path, *, client, model_id: str,
                  whisper, project: str, langsmith=None, on_stage=lambda text: None) -> dict:
    """One uploaded video in, one decision out."""
    build_upload_pack(video, title, pack_dir, whisper, on_stage)
    on_stage(f"Asking Gemini {RUNS_PER_CLIP} times and checking each answer")
    with tracing.traced(langsmith, project):
        return decide_pack(client, model_id, pack_dir, is_news_report)


def setup() -> dict:
    """Everything decide_upload needs that isn't about one clip. Keys from .env, names from config.yaml."""
    from faster_whisper import WhisperModel  # slow import

    load_dotenv(ROOT / ".env")
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    return {
        "client": genai.Client(api_key=os.environ["GEMINI_API_KEY"]),
        "model_id": config["gemini_model"],
        "whisper": WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8"),
        "project": config["langsmith_project"],
        "langsmith": tracing.connect(config["langsmith_project"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--news", action="store_true", help="the upload is marked as a news report")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        result = decide_upload(args.video, args.title, args.news, Path(folder), **setup(), on_stage=print)
    result.pop("log")
    print(json.dumps(result, indent=2))
