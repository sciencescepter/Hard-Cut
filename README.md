# Hard Cut

Applied AI Engineer project (Zero University).

## Contents

- `Data/Reviewer-Labelled Clip Set (12 clips).csv`: hand-labelled reviewer clip set.
- `YouTube Community Guidelines - Enforcement Extract.md`: the guideline sections the reviewers cite.

API keys go in a local `.env` file, which git ignores and is never committed.

## Moderation policy v1.0

- [policy/policy_v1.0.md](policy/policy_v1.0.md): the ruleset. Each rule has an ID (`CSAM-ADJ`, `SH`, `DNG`, `VIO`, `NEWS`), an action and a concrete threshold.
- [policy/label_rule_map.csv](policy/label_rule_map.csv): each of Lena's 12 labels mapped to the rule behind it. The policy gives her decision on all 12.
- [policy/PROMPT_NOTE.md](policy/PROMPT_NOTE.md): what Claude was given, what was asked and how the rules were set.
