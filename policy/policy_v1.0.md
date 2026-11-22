# Hard Cut moderation policy v1.0

**Status:** first version, 2026-11-21
**Built from:**
- `YouTube Community Guidelines - Enforcement Extract.md` (the guideline)
- `Data/Reviewer-Labelled Clip Set (12 clips).csv` (Lena's 12 reviewer labels)

**Label map:** [label_rule_map.csv](label_rule_map.csv)
**How it was made:** [PROMPT_NOTE.md](PROMPT_NOTE.md)

Every clip gets exactly one action: `allow`, `restrict` (age-restricted, signed-in viewers aged 18 or over only) or `remove`. The guideline says content is removed when it "explicitly violates" a section. This policy replaces that phrase with concrete thresholds a reviewer, or a model, can check against the clip's transcript, captions, title and timestamps.

## Rule families

| Prefix | Covers | Guideline section |
|---|---|---|
| `CSAM-ADJ` | Child safety: minors sexualised, endangered or targeted | Child safety policy |
| `SH` | Suicide and self-harm | Suicide and self-harm policy |
| `DNG` | Dangerous acts and chemicals viewers could copy | Harmful or dangerous content policy |
| `VIO` | Real and fictional violence | Violent or graphic content policy |
| `NEWS` | News, documentary, educational and clinical context | EDSA exception |

`DNG` is an addition to the four families in the brief (VIO, CSAM-ADJ, SH, NEWS). The guideline has a separate dangerous-acts section, and one of Lena's removals (CLIP-002) falls under it and no other family.

## Terms used in the thresholds

- **Minor:** anyone who appears to be under 18.
- **Harm span:** the seconds where the harmful act or injury is visible or audible, from first to last frame. It does not include narration that introduces or sums it up.
- **Graphic:** visible blood, an open or fresh wound, a serious injury as it happens, a dead body, or the moment of death.
- **Glorifying signal:** captions, music, sound effects, laughter or commentary that present the harm as exciting, funny, beautiful or deserved. Also emoji overlays and cheering.
- **Replay:** the same moment of harm shown more than once, or in slow motion.
- **Context signal** (counted in `NEWS-01`): reporter, anchor or narrator voice explaining the footage; outlet branding or a chyron; an informational title that describes the event rather than celebrates it; an expert (surgeon, clinician, researcher) explaining what is shown.

## Order of checks

Check the families in this order and stop at the first rule that applies. A higher rule always wins.

1. `CSAM-ADJ-01` to `-03`: **remove**
2. `SH-01` to `-03`: **remove**
3. `DNG-01`: **remove**
4. `VIO-01` to `-03`: **remove**
5. `NEWS-02`, `NEWS-03`, `VIO-04`, `SH-04`, `DNG-02`: **restrict**
6. `CSAM-ADJ-04`, `NEWS-04`, `VIO-05`, `VIO-06`, `SH-05`: **allow**
7. No rule fits: **send to a human reviewer.** Never guess a label.

Context (`NEWS`) is only checked at step 5 onwards, so it can never rescue a clip that has hit a remove rule in steps 1 to 3. At step 4 it can: real violence inside a qualifying news report is judged under `NEWS-02`, unless it is glorified or replayed (see `NEWS-05`).

---

## CSAM-ADJ: child safety

No `CSAM-ADJ` remove rule can be lowered to `restrict`. An age gate does not protect the child on screen.

| ID | Action | Threshold: the rule applies when |
|---|---|---|
| `CSAM-ADJ-01` | remove | A minor is shown with sexualising framing (camera lingering on the body, suggestive poses, revealing clothing as the focus), **or** the title, captions or pinned comments sexualise a minor. Any one is enough. |
| `CSAM-ADJ-02` | remove | A minor is shown in real danger, distress, harm or humiliation for **any length of time**. Examples: on or in a moving vehicle outside a seat, at heights without protection, near fire, water or traffic unsupervised, crying from fear or pain while being filmed, a stunt, dare or challenge with a risk of injury. Framing it as funny ("lol", laughter, prank) makes it worse, never better. |
| `CSAM-ADJ-03` | remove | Packaging targets children (cartoon characters, nursery themes, kid-aimed wording such as "for kids", bright toy thumbnails) **and** the video contains violence, sexual content, frightening scenes or other mature themes. This applies even if the video alone would only be restricted. |
| `CSAM-ADJ-04` | allow | Minors appear only in an ordinary setting (family life, school, organised sport, performance), fully clothed, with no sexualising framing, no danger and no sexualising comments. |

## SH: suicide and self-harm

Intent ("awareness", "my story") never makes graphic self-harm imagery acceptable.

| ID | Action | Threshold: the rule applies when |
|---|---|---|
| `SH-01` | remove | A **fresh** self-harm wound, the act itself, or a blade or tool shown with wounds appears on screen for **any length of time**. Fresh means open, bleeding, scabbing or bandaged after recent harm. Also footage of a suicide or its aftermath shown without news context. |
| `SH-02` | remove | Self-harm or suicide is promoted or romanticised: aesthetic or soft music, "aesthetic"/"routine" framing, glamorising captions, or encouragement. Also self-harm challenges, dares and games. |
| `SH-03` | remove | Any method, instruction or tip for suicide or self-harm, including how to hide it from others. |
| `SH-04` | restrict + crisis panel | Recovery, clinical, educational or news framing **and** self-harm imagery limited to **healed** scars (flat, faded, no fresh wound), shown for **10 seconds or less** in total, with no method described. |
| `SH-05` | allow + crisis panel | Recovery, clinical, educational or news discussion with **no** self-harm imagery at all. *(No labelled example yet.)* |

## DNG: dangerous acts viewers could copy

| ID | Action | Threshold: the rule applies when |
|---|---|---|
| `DNG-01` | remove | **Any one** of: (a) mixing household or other chemicals that make toxic gas or an explosive reaction, e.g. bleach with ammonia, bleach with acid or vinegar; (b) inhaling fumes, choking, suffocation or a "blackout" challenge; (c) instructions for weapons or explosives; (d) a risky act shown **with** how-to steps, "safe" tips or a call to try it. A copycat risk is presumed when the setting is everyday (a kitchen or bedroom), the materials are household items, or the title is light-hearted ("fun", "easy", "try this"). A minor performing the act also falls under `CSAM-ADJ-02`. Instructional or "experiment" framing never excuses it. |
| `DNG-02` | restrict | A dangerous act is shown **only** to warn viewers or to report a real incident, **and** no step, quantity or method is shown that would let someone repeat it. *(No labelled example yet.)* |

## VIO: violence

| ID | Action | Threshold: the rule applies when |
|---|---|---|
| `VIO-01` | remove | Real violence presented as entertainment, with **any one** of: (a) a compilation of more than one separate violent incident; (b) the harm span covers **half or more** of the clip; (c) **2 or more** replays of a moment of harm; (d) any glorifying signal; (e) blows continuing on a person who is down or defenceless. No context signal is present, or it doesn't cover the violent footage. |
| `VIO-02` | remove | Violence against an identifiable person or group is glorified or celebrated, or its victims are mocked or taunted, **whatever** the context. |
| `VIO-03` | remove | A corpse, fatal wound or dismemberment is shown with no qualifying context (`NEWS-01`), or with close-ups held on it beyond what is needed to show what happened. |
| `VIO-04` | restrict | Real violence outside sanctioned sport (see `VIO-06`) with **all** of: a single incident; a harm span of **10 seconds or less**; non-fatal and not graphic beyond brief contact (a punch, shove or strike); no replays; no glorifying signal. Applies even when the only framing is a descriptive title (e.g. "caught on dashcam"). |
| `VIO-05` | allow | The violence or injury is clearly fictional: prosthetics, special-effects makeup, fake blood, film or game footage, with nothing real shown at any point. |
| `VIO-06` | allow | Sanctioned combat sport: a referee or official, an organised event, and any knockout or injury shown at normal speed, for **5 seconds or less**, with no close-up held on blood or injury and no glorifying signal. Unsanctioned street fights are judged under `VIO-01`/`VIO-04`. |

## NEWS: news, documentary and clinical context

`NEWS-01` is a test, not an action. The other `NEWS` rules use it.

| ID | Action | Threshold: the rule applies when |
|---|---|---|
| `NEWS-01` | test | Context qualifies when **2 or more** context signals are present **and** they run across the harmful footage, not only in an opening disclaimer. A single signal (e.g. a news channel name alone, or a disclaimer card) is not enough. |
| `NEWS-02` | restrict | `NEWS-01` is met **and** the clip shows real graphic or distressing harm: conflict, crime, protest, disaster, an assault or its bloody aftermath. Death or a fatal wound may stay under this rule only if shown briefly and not in close-up. |
| `NEWS-03` | restrict | `NEWS-01` is met for a documentary or educational clip **and** the graphic span is **more than 5 seconds**, or includes close-ups of open wounds, surgery or bodily fluids. |
| `NEWS-04` | allow | `NEWS-01` is met for a clinical, educational or documentary clip **and** any graphic moment is **5 seconds or less**, clinically framed (expert narration, medical setting) and not in a lingering close-up. |
| `NEWS-05` | void | Context is cancelled, and the clip is judged as if it had none, when it shows any glorifying signal, 2 or more replays of the harm, music or slow motion over the harm, lingering close-ups on identifiable victims, or is a re-upload with the narration and branding cut away. Context never applies to `CSAM-ADJ`, `SH-01` to `SH-03`, or `DNG-01`. |

---

## Evidence each decision must carry

1. **Rule ID**, e.g. `VIO-04`. For `restrict` and `allow` decisions that passed a higher check, name that rule too (e.g. `NEWS-01` + `NEWS-02`).
2. **Harm span** in seconds, start before end, both inside the clip's length. Leave it empty only when no harm is shown at all.
3. **The threshold that was met**, in a few words (e.g. "single punch, 2s, no replay").
4. For `restrict` via context: **which context signals** and where they appear.

## Known limits of v1.0

- Built from **12 clips labelled by one reviewer**. `SH-05` and `DNG-02` have no labelled example, so their thresholds come from the guideline alone.
- The time limits are set with room above the spans Lena labelled under each rule: `VIO-04` 10 s (CLIP-004 was 2 s), `SH-04` 10 s (CLIP-010 was 3 s), `VIO-06` 5 s (CLIP-012 was 3 s), `NEWS-04` 5 s (CLIP-006 was 4 s). They are starting points to test, not settled values.
- `VIO-04` restricts short, plain real violence with no news context (CLIP-004). The guideline's wording ("needs enough context") could be read as pointing to remove instead. Lena's label is followed here, and the point should be confirmed.
