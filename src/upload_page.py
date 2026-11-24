"""The upload decision page. Runs on this computer only: http://127.0.0.1:5050

It saves the uploaded clip, calls decide_upload() from the upload decision script
in the background, and shows what comes back. It makes no decisions of its own.

Usage:
  .venv/bin/python src/upload_page.py
"""

import json
import re
import shutil
import sys
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

from build_packs import VIDEO_SUFFIXES, probe
from upload_decision import ROOT, ROUTED, decide_upload, setup

UPLOADS = ROOT / "uploads"
PORT = 5050
MAX_UPLOAD_MB = 300
MAX_CLIP_SECONDS = 600  # longer clips would take many minutes and many tokens
UPLOAD_ID = re.compile(r"[0-9a-f]{32}")


def routed(reason: str) -> dict:
    """The result for a clip that broke on the way: no label, a person looks at it."""
    return {"decision": None, "age_restricted": False, "reasoning": None, "findings": [],
            "validation_status": ROUTED, "routed_reason": reason, "langsmith_trace_url": None}


def create_app(dependencies: dict, uploads: Path = UPLOADS, test_mode: str = "") -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    app.config["TRUSTED_HOSTS"] = ["127.0.0.1", "localhost"]
    worker = ThreadPoolExecutor(1)  # one clip at a time; the next one waits
    jobs: dict[str, dict] = {}

    def save(job: dict) -> None:
        (uploads / job["id"] / "job.json").write_text(json.dumps(job, indent=2) + "\n")

    for path in uploads.glob("*/job.json"):
        job = json.loads(path.read_text())
        if job["result"] is None:  # the page was closed while this clip was being worked on
            job["result"] = routed("The page was stopped before this clip was finished.")
        jobs[job["id"]] = job

    def work(job: dict, video: Path) -> None:
        def on_stage(text: str) -> None:
            job["stage"] = text

        try:
            result = decide_upload(video, job["title"], job["is_news_report"], uploads / job["id"],
                                   **dependencies, on_stage=on_stage)
            log = result.pop("log")
            (uploads / job["id"] / "log.json").write_text(json.dumps(log, indent=2) + "\n")
        except Exception as error:
            traceback.print_exc()
            result = routed(f"The clip could not be processed ({type(error).__name__}).")
        job["seconds_taken"] = round(time.time() - job["started"])
        job["result"] = result
        save(job)

    def get_job(upload_id: str) -> dict:
        if not UPLOAD_ID.fullmatch(upload_id) or upload_id not in jobs:
            abort(404)
        return jobs[upload_id]

    def home(error: str = "", status: int = 200):
        recent = sorted(jobs.values(), key=lambda job: job["started"], reverse=True)
        queue = [j for j in recent if j["result"] and j["result"]["validation_status"] == ROUTED]
        return render_template("home.html", recent=recent, queue=queue, error=error, test_mode=test_mode,
                               max_minutes=MAX_CLIP_SECONDS // 60), status

    @app.get("/")
    def index():
        return home()

    @app.errorhandler(413)
    def too_big(_):
        return home(f"That file is larger than {MAX_UPLOAD_MB} MB.", 413)

    @app.post("/uploads")
    def upload():
        file, title = request.files.get("clip"), request.form.get("title", "").strip()
        suffix = Path(file.filename or "").suffix.lower() if file else ""
        if suffix not in VIDEO_SUFFIXES:
            return home("Choose a video file (" + ", ".join(sorted(VIDEO_SUFFIXES)) + ").", 400)
        if not title:
            return home("Give the clip a title.", 400)

        upload_id = uuid.uuid4().hex
        folder = uploads / upload_id
        folder.mkdir(parents=True)
        video = folder / f"source{suffix}"
        file.save(video)
        try:
            duration, _ = probe(video)
            problem = "" if duration <= MAX_CLIP_SECONDS else f"That clip is longer than {MAX_CLIP_SECONDS // 60} minutes."
        except Exception:
            problem = "That file could not be read as a video."
        if problem:
            shutil.rmtree(folder)
            return home(problem, 400)

        job = {"id": upload_id, "title": title, "is_news_report": "is_news_report" in request.form,
               "duration_seconds": round(duration, 2), "started": time.time(), "stage": "Waiting to start", "result": None}
        jobs[upload_id] = job
        save(job)
        worker.submit(work, job, video)
        return redirect(url_for("show", upload_id=upload_id), 303)

    @app.get("/uploads/<upload_id>")
    def show(upload_id):
        return render_template("decision.html", job=get_job(upload_id), test_mode=test_mode)

    @app.get("/uploads/<upload_id>/status")
    def status(upload_id):
        job = get_job(upload_id)
        return jsonify(done=job["result"] is not None, stage=job["stage"], seconds=int(time.time() - job["started"]))

    @app.get("/uploads/<upload_id>/frames/<name>")
    def frame(upload_id, name):
        get_job(upload_id)
        return send_from_directory(uploads / upload_id / "frames", name)

    return app


if __name__ == "__main__":
    UPLOADS.mkdir(exist_ok=True)
    print("Loading Whisper and connecting...", flush=True)
    deps = setup()
    if deps["langsmith"] is None:
        print("LangSmith tracing is OFF: add LANGSMITH_API_KEY to .env to turn it on.", file=sys.stderr)
    create_app(deps).run(host="127.0.0.1", port=PORT, threaded=True)
