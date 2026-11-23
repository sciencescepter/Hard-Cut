# Evidence packs: note

Run summary: [packs_summary.md](packs_summary.md). Match list: [xd_matches.csv](xd_matches.csv). Builder: [src/build_packs.py](../src/build_packs.py).

## XD-Violence clip per clip_id

Each of Lena's 12 clips is paired with one video from the XD-Violence test set, because her original footage is not available. XD-Violence only covers fighting, shooting, riots, abuse, car accidents and explosions, so 5 clips have a real category match, 1 a fiction match, 2 the closest setting or format, and 4 only a non-violent stand-in. Every pick was checked against its frames after the build.

| clip_id | Lena's clip | XD-Violence video | Why it fits |
|---|---|---|---|
| CLIP-001 | street fight compilation #4 (remove) | `v=SE5fxK7SasU__#00-03-23_00-04-08_label_B4-0-0` | Real crowd violence posted as entertainment: a cheering crowd smashes and climbs on a car while dozens film on phones. One incident in this 45 s segment, not several cuts. |
| CLIP-002 | fun kitchen experiment (remove) | `v=5AlAh8J3WqE__#1_label_A` | **Stand-in only.** No dangerous-chemicals category exists. A non-violent food vlog stands in for the everyday indoor setting. |
| CLIP-003 | Ava's first gymnastics meet!! (allow) | `v=hdy5kZ5dwj8__#1_label_A` | A minor in an ordinary organised-sport setting (a youth hockey goalie being kitted out), with nothing harmful. No XD Abuse video was considered for a child clip. |
| CLIP-004 | Road rage caught on dashcam - Mumbai (restrict) | `v=OE9t3XImErk__#1_label_B1-0-0` | One short real assault on a street at night, filmed on a phone, with a graphic-content warning card and no news narration. XD marks one violent span, 8-12 s. |
| CLIP-005 | night routine aesthetic vlog (remove) | `v=qV4YYnXdQCc__#00-03-00_00-06-00_label_A` | **Stand-in only.** No self-harm category exists. A non-violent night-time walking vlog stands in for the vlog format. |
| CLIP-006 | How surgeons treat severe burns, Documentary (allow) | `v=a0TQkX_zLt0__#1_label_A` | **Stand-in only.** No medical footage exists. A narrated documentary-style video stands in for the documentary framing. |
| CLIP-007 | Protest clash in city centre - evening bulletin (restrict) | `v=UzxuX79xq4s__#1_label_B4-0-0` | A DW News report on violent yellow-vest protests in Paris: anchor, journalist voice-over and chyron throughout. XD marks three violent spans. |
| CLIP-008 | zombie bite SFX makeup tutorial (allow) | `v=FW_qbiPH7UA__#1_label_B1-0-0` | Staged film violence (The Expendables) with fake blood and nothing real. XD labels it violent because it does not separate fiction from real footage. |
| CLIP-009 | toddler rides the roof rack lol (remove) | `v=-tqHsoEoUyY__#1_label_A` | **Stand-in only.** No child-endangerment category exists, and no Abuse video was considered. Ordinary driving footage from inside a car stands in for the moving-car setting. |
| CLIP-010 | my recovery story - 2 years clean (restrict) | `v=Pf7WtK-YPDA__#1_label_A` | A person talking to camera about a harmful event (a TMZ Sports street interview), with no harmful imagery, like a recovery story told to camera. |
| CLIP-011 | Stabbing outside Birmingham New Street - local news update (restrict) | `v=GI49YSCruwY__#1_label_B4-0-0` | A Guardian news report on police violence against voters in Catalonia, with injured people and on-screen captions. XD has no stabbing footage. XD marks three violent spans. |
| CLIP-012 | Amateur MMA bout - full fight Sao Paulo (allow) | `v=osjdmjNJUdg__#1_label_B1-0-0` | A fight inside a sanctioned professional game (NHL) with officials stepping in. XD has no MMA footage. XD marks two violent spans. |

## Key prompt

The script was written by Claude Code from this request:

> "make an evidence pack for each clip with pictures every 2 seconds, with timestamps, with a timed transcript, which will be checked by the gemini API. pick matching xd violence file for each, get script from claude code, run on all 12 with a summary, push it all."

The project then named the toolset to use: ffmpeg for the frames and faster-whisper for the transcript. It also placed the Gemini check in a later stage (the decision script), so this stage builds the packs that check will read.

## What was changed in the output

- **Timestamps on the frames.** Each frame is named by its second (`t0042s.jpg`) and has `t=00:42 (42s)` printed in its top-left corner, so the time survives if a picture is viewed on its own.
- **Audio decoding.** faster-whisper's own decoder crashed with the installed PyAV version, so the audio is decoded with ffmpeg (16 kHz mono) and passed to Whisper directly. The transcript content is unaffected.
- **Empty transcripts kept empty.** CLIP-001, 004, 005 and 009 have no speech. With the voice filter off, Whisper invented text such as "Stay tuned for more of these kind of events"; that output was rejected rather than saved.
- **Three match descriptions corrected after viewing the frames.** CLIP-001 is one incident, not a compilation. CLIP-004 opens with a graphic-content warning card. CLIP-011 is a Guardian report.
- **An answer key in each pack.json, kept separate.** Lena's label and XD-Violence's violent segments (converted from frame numbers to seconds at 24 fps) are stored under `answer_key`, so a later decision script can be checked against them without being shown them.
- **Frames and videos not committed.** They are stills of real violence from a dataset with no stated licence, so they stay on the machine that built them. The repo holds the transcripts, pack.json files, summary and script, which rebuild the frames exactly.
- **No Gemini call in this stage.** A Gemini decision run was started and then stopped, because the decision step belongs to a later stage. Its partial results are not part of this deliverable.
