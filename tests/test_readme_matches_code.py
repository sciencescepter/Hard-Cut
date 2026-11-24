"""The README shows the prompt and the finding fields so reviewers can read them. Keep them true to the code."""

from pathlib import Path

from classify_clips import INSTRUCTIONS
from decision_schema import ClipDecision, Finding

README = (Path(__file__).resolve().parent.parent / "README.md").read_text()


def test_readme_shows_the_exact_prompt():
    assert INSTRUCTIONS.rstrip() in README


def test_readme_lists_every_finding_field():
    for field in [*ClipDecision.model_fields, *Finding.model_fields]:
        assert f"| `{field}` |" in README, field
