# Prompt note: how policy v1.0 was made

**Files Claude worked from (and nothing else):**
- `YouTube Community Guidelines - Enforcement Extract.md`
- `Data/Reviewer-Labelled Clip Set (12 clips).csv` (Lena's 12 labels)

**What was asked:**
- Write a ruleset for classifying clips as `allow`, `restrict` or `remove`.
- Give every rule an ID across VIO, CSAM-ADJ, SH and NEWS.
- Replace the guideline's "explicitly violated" with concrete thresholds, such as repeated violence, blades and blood, or dangerous chemicals kids could copy.
- Map each of Lena's labels to the rules behind it.

**How it was built:**
1. The rule families and actions come from the guideline's sections and its three-action table.
2. Each threshold was written so that it can be checked against a clip's title, transcript, captions and timestamps: counts (replays, incidents, context signals), time limits in seconds, and named items (bleach with ammonia, fresh wounds, roof racks).
3. Lena's notes and harm spans set where each line falls. For example, her 2-second dashcam punch (CLIP-004) set `VIO-04`, and her 4-second clinical burn shot (CLIP-006) set `NEWS-04`.
4. Each of the 12 clips was then run through the order of checks by hand. All 12 land on Lena's decision ([label_rule_map.csv](label_rule_map.csv)).

**Change from the brief:** a fifth family, `DNG`, was added, because CLIP-002 (bleach and ammonia) falls under the guideline's dangerous-acts section and no other family.

**To use it as a classifier prompt:** give the model `policy_v1.0.md` and one clip's title, transcript, frame captions and duration. Ask for the action, the deciding rule ID, the harm span in seconds and the threshold met. Tell it to answer "human review" when no rule fits, never to guess. Never send Lena's label columns, or the answers leak.
