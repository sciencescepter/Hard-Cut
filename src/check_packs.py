"""Check that every timestamp in the evidence packs points at a real moment.

Checks, for each pack in evidence/packs/:
  1. Frames: each frame's second is inside the video, its file name carries
     the same second, and the file exists (when frames are built locally).
  2. Transcript: every line has 0 <= start < end <= the video's length, the
     lines run in order, and transcript.txt shows exactly the times in
     transcript.json (no rounding).
  3. XD-Violence segments: inside the video, start before end.
  4. With --video: each frame really is the picture at its second. The saved
     frame is compared with the frame decoded by number (second x fps), so a
     seek that landed on the wrong moment would show up as a mismatch.

Exits with an error if anything fails.

Usage:
  .venv/bin/python src/check_packs.py           # timestamp checks
  .venv/bin/python src/check_packs.py --video   # also compare frames with the video
"""

import io
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from build_packs import FRAME_WIDTH, PACKS, find_video

LABEL = re.compile(r"^\[(\d{2}):(\d{2}\.\d{2})-(\d{2}):(\d{2}\.\d{2})\] ")
MAX_PIXEL_DIFFERENCE = 6.0  # mean difference per channel, 0-255, below the stamped box


def frames_by_number(video: Path, numbers: list[int]) -> list[Image.Image]:
    """Decode the video once and return the frames with these numbers, in order.

    The frames are evenly spaced (every 2 s), so one ffmpeg select picks every
    step-th frame by its number, counted from the first frame.
    """
    step = numbers[1] - numbers[0] if len(numbers) > 1 else 1
    if any(b - a != step for a, b in zip(numbers, numbers[1:])) or numbers[0] != 0:
        raise ValueError("frame numbers are not evenly spaced from 0")
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video),
         "-vf", f"select=not(mod(n\\,{step})),scale={FRAME_WIDTH}:-2",
         "-fps_mode", "passthrough", "-f", "image2pipe", "-vcodec", "bmp", "-"],
        capture_output=True,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode()[-300:])
    images, data = [], out.stdout
    while data:
        size = int.from_bytes(data[2:6], "little")  # each BMP header holds its own size
        images.append(Image.open(io.BytesIO(data[:size])).convert("RGB"))
        data = data[size:]
    return images[: len(numbers)]


def check_pack(pack_dir: Path, compare_video: bool) -> list[str]:
    problems = []
    pack = json.loads((pack_dir / "pack.json").read_text())
    duration = pack["source"]["duration_seconds"]
    fps = pack["source"]["fps"]

    for frame in pack["frames"]["items"]:
        t = frame["t"]
        if not 0 <= t < duration:
            problems.append(f"frame t={t:g}s is outside the video (0-{duration}s)")
        if frame["file"] != f"frames/t{int(t):04d}s.jpg":
            problems.append(f"frame t={t:g}s is stored as {frame['file']}")

    segments = json.loads((pack_dir / "transcript.json").read_text())["segments"]
    previous_start = -1.0
    for s in segments:
        if not 0 <= s["start"] < s["end"] <= duration:
            problems.append(f"transcript line {s['start']}-{s['end']}s is not inside the video (0-{duration}s)")
        if s["start"] < previous_start:
            problems.append(f"transcript line at {s['start']}s is out of order")
        previous_start = s["start"]

    lines = [l for l in (pack_dir / "transcript.txt").read_text().splitlines() if l != "(no speech detected)"]
    if len(lines) != len(segments):
        problems.append(f"transcript.txt has {len(lines)} lines, transcript.json has {len(segments)}")
    for line, s in zip(lines, segments):
        m = LABEL.match(line)
        if not m:
            problems.append(f"transcript.txt label can't be read: {line[:30]}")
            continue
        start = int(m[1]) * 60 + float(m[2])
        end = int(m[3]) * 60 + float(m[4])
        if abs(start - s["start"]) > 0.005 or abs(end - s["end"]) > 0.005:
            problems.append(f"transcript.txt shows {m[1]}:{m[2]}-{m[3]}:{m[4]} but the line is {s['start']}-{s['end']}s")

    for seg in pack["answer_key"]["xd_violent_segments"]:
        if not 0 <= seg["start"] < seg["end"] <= duration + 1 / fps:
            problems.append(f"XD segment {seg['start']}-{seg['end']}s is not inside the video (0-{duration}s)")

    frames_present = all((pack_dir / f["file"]).exists() for f in pack["frames"]["items"])
    if compare_video and frames_present:
        video = find_video(pack["source"]["xd_video"])
        items = pack["frames"]["items"]
        truths = frames_by_number(video, [round(f["t"] * fps) for f in items])
        if len(truths) != len(items):
            problems.append(f"decoded {len(truths)} frames from the video, expected {len(items)}")
        for frame, truth in zip(items, truths):
            saved = Image.open(pack_dir / frame["file"]).convert("RGB")
            top = saved.height // 8  # skip the stamped timestamp box
            box = (0, top, saved.width, saved.height)
            diff = ImageStat.Stat(ImageChops.difference(saved.crop(box), truth.resize(saved.size).crop(box))).mean
            if sum(diff) / 3 > MAX_PIXEL_DIFFERENCE:
                problems.append(f"frame t={frame['t']:g}s does not match the video's picture at that second")
    elif compare_video:
        problems.append("frames are not built on this machine, so they could not be compared with the video")
    return problems


def main(compare_video: bool, selected: list[str]) -> None:
    failed = 0
    for pack_dir in sorted(p for p in PACKS.iterdir() if (p / "pack.json").exists()):
        if selected and pack_dir.name not in selected:
            continue
        problems = check_pack(pack_dir, compare_video)
        pack = json.loads((pack_dir / "pack.json").read_text())
        segments = len(json.loads((pack_dir / "transcript.json").read_text())["segments"])
        status = "OK" if not problems else f"{len(problems)} PROBLEM(S)"
        print(f"{pack_dir.name}: {pack['frames']['count']} frames, {segments} transcript lines, "
              f"{len(pack['answer_key']['xd_violent_segments'])} XD segments | {status}")
        for problem in problems:
            print(f"    - {problem}")
        failed += bool(problems)
    print(f"\n{'All packs passed' if not failed else f'{failed} pack(s) failed'}"
          f"{' (frames compared with the video)' if compare_video else ''}.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    args = sys.argv[1:]
    main("--video" in args, [a for a in args if not a.startswith("--")])
