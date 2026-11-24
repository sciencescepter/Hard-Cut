"""LangSmith tracing for upload decisions. Off unless LANGSMITH_API_KEY is in .env.

The pictures are never sent to LangSmith: they can be stills of real violence.
A trace holds the prompt text, the frame timestamps, Gemini's replies, the
Pydantic errors and the token counts.
"""

import os
import sys
from contextlib import contextmanager

from langsmith import Client, get_current_run_tree
from langsmith.run_helpers import tracing_context


def contents_as_text(contents: list) -> list[dict]:
    """The messages sent to Gemini, with each picture replaced by a short note."""
    return [
        {"role": content.role,
         "parts": [part.text if part.text is not None else "[picture not stored in the trace]" for part in content.parts]}
        for content in contents
    ]


def connect(project: str) -> Client | None:
    """A LangSmith client with the project ready, or None if no key is set or it can't be reached."""
    key = os.environ.get("LANGSMITH_API_KEY", "").strip()
    if not key:
        return None
    try:
        client = Client(api_key=key)
        if not client.has_project(project):
            client.create_project(project)
        return client
    except Exception as error:  # tracing must never stop a decision
        print(f"LangSmith is not available ({type(error).__name__}), so this run is not traced", file=sys.stderr)
        return None


@contextmanager
def traced(client: Client | None, project: str):
    with tracing_context(enabled=client is not None, client=client, project_name=project):
        yield
    if client is not None:
        client.flush()


def current_trace_id() -> str | None:
    run = get_current_run_tree()
    return str(run.trace_id) if run is not None else None


def save_final_call(client: Client | None, trace_id: str | None, decision: str, agrees: bool | None) -> bool:
    """Attach the reviewer's final call to the trace as feedback. Names and notes stay on this computer."""
    if client is None or trace_id is None:
        return False
    try:
        client.create_feedback(trace_id, key="reviewer_final_call", value=decision,
                               score=None if agrees is None else int(agrees))
        return True
    except Exception as error:  # the call is already saved locally
        print(f"could not add the final call to LangSmith ({type(error).__name__})", file=sys.stderr)
        return False


def current_trace_url() -> str | None:
    """The link to the trace being recorded now, or None when tracing is off or the link can't be made."""
    run = get_current_run_tree()
    if run is None:
        return None
    try:
        return run.get_url()
    except Exception as error:
        print(f"could not get the LangSmith link ({type(error).__name__})", file=sys.stderr)
        return None
