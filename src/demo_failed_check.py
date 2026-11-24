"""The same page, with Gemini replaced by a stand-in whose answer always fails the Pydantic check.

For testing how a failed answer is shown. Everything else is the real code: the same
evidence pack, retry, check, vote and page. A banner says it is test mode. No API calls.

Usage:
  .venv/bin/python src/demo_failed_check.py      # http://127.0.0.1:5051
"""

import json
from types import SimpleNamespace

from upload_decision import ROOT, setup
from upload_page import create_app

BAD_ANSWER = json.dumps({
    "action": "remove", "rule_id": "VIO-99", "threshold_met": "x", "context_signals": [], "findings": [], "reasoning": "x"})


class BadGemini:
    """Cites a rule that isn't in the policy, so the answer can never pass."""

    @property
    def models(self):
        return self

    def generate_content(self, model, contents, config):
        usage = SimpleNamespace(prompt_token_count=0, candidates_token_count=0, total_token_count=0)
        return SimpleNamespace(text=BAD_ANSWER, usage_metadata=usage)


if __name__ == "__main__":
    folder = ROOT / "uploads" / "test_mode"
    folder.mkdir(parents=True, exist_ok=True)
    dependencies = {**setup(), "client": BadGemini(), "model_id": "stand-in (always fails the check)"}
    create_app(dependencies, folder, "TEST MODE: Gemini is replaced by an answer that always fails the check").run(
        host="127.0.0.1", port=5051)
