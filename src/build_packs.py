"""Build one evidence pack per clip_id from its matched XD-Violence video.

For each row in evidence/xd_matches.csv this script:
  1. finds the XD-Violence video under xd_violence/ (any subfolder),
  2. saves one frame every 2 seconds, with the timestamp in the file name and
     printed on the picture (ffmpeg),
  3. writes a timed transcript of the audio (faster-whisper),
  4. writes pack.json: the clip details, the source video and XD-Violence's own
     violent segments (in seconds) for checking afterwards.

Output: evidence/packs/<clip_id>/{frames/, transcript.json, transcript.txt, pack.json}

Usage:
  .venv/bin/python src/build_packs.py            # all 12
  .venv/bin/python src/build_packs.py CLIP-004   # one or more clip_ids
"""

import csv
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
MATCHES = ROOT / "evidence" / "xd_matches.csv"
LENA = ROOT / "Data" / "Reviewer-Labelled Clip Set (12 clips).csv"
XD_DIR = ROOT / "xd_violence"
ANNOTATIONS = XD_DIR / "lists" / "annotations.txt"
PACKS = ROOT / "evidence" / "packs"

FRAME_EVERY_SECONDS = 2
FRAME_WIDTH = 640
WHISPER_MODEL = "small"  # downloaded from Hugging Face on first use, about 470 MB
VIDEO_SUFFIXES = {".mp4", ".mkv", ".avi", ".webm", ".mov"}


def mmss(seconds: float) -> str:
    """Whole-second label for a frame. Frames are only taken at whole seconds."""
    seconds = int(seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def mmss_exact(seconds: float) -> str:
    """Transcript label with the exact hundredths Whisper reported, never rounded.

    Rounding to whole seconds made labels that don't exist: a line ending at
    96.58 s became 01:37 on a 96.67 s video, and a 0.26 s line became 04:26-04:26.
    """
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes):02d}:{rest:05.2f}"


def find_video(xd_name: str) -> Path:
    matches = [p for p in XD_DIR.rglob("*") if p.suffix.lower() in VIDEO_SUFFIXES and p.stem == xd_name]
    if len(matches) != 1:
        raise FileNotFoundError(f"expected one video named {xd_name!r} under {XD_DIR}, found {len(matches)}")
    return matches[0]


def probe(video: Path) -> tuple[float, float]:
    """Return (duration_seconds, frames_per_second)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=avg_frame_rate:format=duration", "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(out.stdout)
    num, den = info["streams"][0]["avg_frame_rate"].split("/")
    return float(info["format"]["duration"]), float(num) / float(den)


def xd_violent_segments(xd_name: str, fps: float) -> list[dict]:
    """XD-Violence's own frame-level annotation for this video, converted to seconds."""
    for line in ANNOTATIONS.read_text().splitlines():
        parts = line.split()
        if parts and parts[0].removesuffix(".mp4") == xd_name:
            frames = [int(x) for x in parts[1:]]
            return [
                {"start_frame": s, "end_frame": e, "start": round(s / fps, 2), "end": round(e / fps, 2)}
                for s, e in zip(frames[::2], frames[1::2])
            ]
    return []  # normal (label A) videos have no annotation line


def stamp(path: Path, seconds: float) -> None:
    """Print the timestamp on the frame, top left, white on a dark box."""
    image = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(image)
    text = f"t={mmss(seconds)} ({seconds:g}s)"
    font = ImageFont.load_default(size=max(16, image.width // 32))
    box = draw.textbbox((8, 8), text, font=font)
    draw.rectangle((box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4), fill=(0, 0, 0))
    draw.text((8, 8), text, fill=(255, 255, 255), font=font)
    image.save(path, quality=85)


def extract_frame(video: Path, seconds: float, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{seconds:.3f}", "-i", str(video),
         "-frames:v", "1", "-vf", f"scale={FRAME_WIDTH}:-2", "-q:v", "3", str(out)],
        check=True,
    )
    stamp(out, seconds)


def build_frames(video: Path, duration: float, folder: Path) -> list[dict]:
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.jpg"):
        old.unlink()
    # Every 2 s from 0, as long as the frame is inside the video.
    times = [float(t) for t in range(0, int(duration) + 1, FRAME_EVERY_SECONDS) if t < duration - 0.05]
    jobs = [(t, folder / f"t{int(t):04d}s.jpg") for t in times]
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda job: extract_frame(video, job[0], job[1]), jobs))
    return [{"t": t, "timestamp": mmss(t), "file": f"frames/{path.name}"} for t, path in jobs if path.exists()]


def load_audio(video: Path):
    """Decode the audio track to 16 kHz mono with ffmpeg. None if the video has no audio."""
    import numpy as np

    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True,
    )
    if out.returncode != 0 or not out.stdout:
        return None
    return np.frombuffer(out.stdout, dtype=np.float32)


def build_transcript(model, video: Path) -> tuple[list[dict], str]:
    # Audio is decoded with ffmpeg rather than faster-whisper's own decoder,
    # which fails with the installed PyAV version.
    audio = load_audio(video)
    if audio is None:
        return [], "none (no audio track)"
    segments, info = model.transcribe(audio, vad_filter=True, beam_size=5)
    lines = [
        {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
        for s in segments
        if s.text.strip()
    ]
    return lines, info.language


def main(selected: list[str]) -> None:
    from faster_whisper import WhisperModel  # slow import, only when building

    lena = {row["clip_id"]: row for row in csv.DictReader(LENA.open())}
    matches = [row for row in csv.DictReader(MATCHES.open()) if not selected or row["clip_id"] in selected]
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

    for match in matches:
        clip_id = match["clip_id"]
        pack_dir = PACKS / clip_id
        video = find_video(match["xd_video"])
        duration, fps = probe(video)
        print(f"{clip_id}: {video.name} ({duration:.1f}s, {fps:g} fps)", flush=True)

        frames = build_frames(video, duration, pack_dir / "frames")
        transcript, language = build_transcript(model, video)

        (pack_dir / "transcript.json").write_text(json.dumps(
            {"language": language, "model": f"faster-whisper {WHISPER_MODEL}", "segments": transcript}, indent=2) + "\n")
        (pack_dir / "transcript.txt").write_text(
            "".join(f"[{mmss_exact(s['start'])}-{mmss_exact(s['end'])}] {s['text']}\n" for s in transcript)
            or "(no speech detected)\n"
        )
        (pack_dir / "pack.json").write_text(json.dumps({
            "clip_id": clip_id,
            "source": {
                "dataset": "XD-Violence (test set)",
                "xd_video": match["xd_video"],
                "title": match["xd_title"],
                "match_type": match["match_type"],
                "why_it_fits": match["why_it_fits"],
                "duration_seconds": round(duration, 2),
                "fps": fps,
            },
            "frames": {
                "every_seconds": FRAME_EVERY_SECONDS,
                "count": len(frames),
                # Frames are stills of real violence: built locally and git-ignored, not in the repo.
                "stored": "local only, not committed; rebuild with src/build_packs.py",
                "items": frames,
            },
            "transcript": {"file": "transcript.json", "segments": len(transcript), "language": language},
            # For checking only. Never sent to Gemini.
            "answer_key": {
                "xd_violent_segments": xd_violent_segments(match["xd_video"], fps),
                "lena": {
                    "clip_title": lena[clip_id]["clip_title"],
                    "decision": lena[clip_id]["reviewer_decision"],
                    "guideline": lena[clip_id]["reviewer_guideline_reference"],
                    "harm_start_seconds": lena[clip_id]["reviewer_harm_start_seconds"],
                    "harm_end_seconds": lena[clip_id]["reviewer_harm_end_seconds"],
                },
            },
        }, indent=2) + "\n")
        print(f"  {len(frames)} frames, {len(transcript)} transcript lines ({language})", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
