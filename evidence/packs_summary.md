# Evidence packs: run summary

Built by `src/build_packs.py` (ffmpeg + faster-whisper `small`, CPU int8) on all 12 clip_ids. One frame every 2 s, with the timestamp in the file name and printed on the picture, plus a timed transcript of the audio. No Gemini or other model API is called.

| clip_id | XD-Violence video | Match | Seconds | Frames | Transcript segments | Language | XD violent segments |
|---|---|---|---|---|---|---|---|
| CLIP-001 | `v=SE5fxK7SasU__#00-03-23_00-04-08_label_B4-0-0` | category match | 45.11 | 23 | 0 | en | 0-45.04s |
| CLIP-002 | `v=5AlAh8J3WqE__#1_label_A` | stand-in (no category match) | 453.54 | 227 | 55 | hi | none (normal video) |
| CLIP-003 | `v=hdy5kZ5dwj8__#1_label_A` | stand-in (closest setting) | 194.75 | 98 | 33 | en | none (normal video) |
| CLIP-004 | `v=OE9t3XImErk__#1_label_B1-0-0` | category match | 23.21 | 12 | 0 | en | 8.04-12.08s |
| CLIP-005 | `v=qV4YYnXdQCc__#00-03-00_00-06-00_label_A` | stand-in (no category match) | 180.11 | 91 | 0 | en | none (normal video) |
| CLIP-006 | `v=a0TQkX_zLt0__#1_label_A` | stand-in (no category match) | 490.17 | 246 | 64 | en | none (normal video) |
| CLIP-007 | `v=UzxuX79xq4s__#1_label_B4-0-0` | category match | 220.25 | 111 | 43 | en | 11.25-35s; 54.67-124.54s; 142.92-194.17s |
| CLIP-008 | `v=FW_qbiPH7UA__#1_label_B1-0-0` | fiction match | 136.81 | 69 | 11 | en | 68.92-86.67s; 98.62-114.38s |
| CLIP-009 | `v=-tqHsoEoUyY__#1_label_A` | stand-in (no category match) | 42.12 | 22 | 0 | en | none (normal video) |
| CLIP-010 | `v=Pf7WtK-YPDA__#1_label_A` | stand-in (closest format) | 81.42 | 41 | 17 | en | none (normal video) |
| CLIP-011 | `v=GI49YSCruwY__#1_label_B4-0-0` | category match | 126.33 | 64 | 10 | ca | 0-58.75s; 74.79-81.88s; 96.67-124.17s |
| CLIP-012 | `v=osjdmjNJUdg__#1_label_B1-0-0` | category match | 96.67 | 49 | 40 | en | 7.96-35.67s; 57.5-82.71s |

- All 12 packs pass `src/check_packs.py --video`: every frame, transcript line and XD segment is inside its video, transcript.txt matches transcript.json exactly, and every saved frame matches the video's picture at that second.
- 4 packs have 0 transcript segments (CLIP-001, 004, 005, 009). Rechecked with the voice filter off: Whisper only produced "Oh", garbled characters or stock filler over music and noise, so there is no real speech and the empty transcript is correct.
- Frames stay on the machine that built them and are not committed: they are stills of real violence from a dataset with no stated licence. Rebuild them with the command below once the XD-Violence test set is in `xd_violence/`.

```bash
.venv/bin/python src/build_packs.py
.venv/bin/python src/check_packs.py --video
```
