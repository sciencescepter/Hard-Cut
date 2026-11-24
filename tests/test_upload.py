"""Offline tests for decide_pack() and the upload page. A fake Gemini stands in for the API.

They use a made-up pack and a short video that ffmpeg generates, so no clip is needed.
"""

import io
import json
import subprocess
import time
from types import SimpleNamespace

import pytest
from PIL import Image

import upload_decision as ud
from upload_page import create_app

FINDING = {"rule_id": "VIO-04", "harm_start_seconds": 2, "harm_end_seconds": 5, "rationale": "A shove <b>is</b> seen.",
           "evidence_frame": 4, "evidence_transcript_line": None}


def answer(action="restrict", rule_id="VIO-04", findings=None):
    return json.dumps({"action": action, "rule_id": rule_id, "threshold_met": "x", "context_signals": [], "reasoning": "Why.",
                       "findings": [{**FINDING, "rule_id": rule_id}] if findings is None else findings})


BAD = answer(rule_id="VIO-99")
REMOVE = answer("remove", "VIO-01")


class FakeGemini:
    def __init__(self, *replies):
        self.replies, self.models, self.prompts = list(replies), self, []

    def generate_content(self, model, contents, config):
        self.prompts.append(contents)
        usage = SimpleNamespace(prompt_token_count=1, candidates_token_count=1, total_token_count=2)
        return SimpleNamespace(text=self.replies.pop(0) if len(self.replies) > 1 else self.replies[0], usage_metadata=usage)


@pytest.fixture
def pack(tmp_path):
    (tmp_path / "frames").mkdir()
    items = []
    for t in range(0, 10, 2):
        Image.new("RGB", (16, 9)).save(tmp_path / "frames" / f"t{t:04d}s.jpg")
        items.append({"t": float(t), "timestamp": f"00:{t:02d}", "file": f"frames/t{t:04d}s.jpg"})
    (tmp_path / "pack.json").write_text(json.dumps({
        "source": {"title": "A clip", "duration_seconds": 10.0}, "frames": {"every_seconds": 2, "count": 5, "items": items}}))
    (tmp_path / "transcript.json").write_text(json.dumps({"segments": [{"start": 1.2, "end": 4.86, "text": "Look out."}]}))
    return tmp_path


def decide(pack, *replies, news=False):
    return ud.decide_pack(FakeGemini(*replies), "test-model", pack, news)


def assert_routed_without_a_label(result):
    assert result["validation_status"] == "routed_to_human_review"
    assert result["decision"] is None and result["findings"] == [] and not result["age_restricted"]
    assert result["reasoning"] is None and result["routed_reason"]


def test_restrict_is_age_restricted_with_a_timed_finding(pack):
    result = decide(pack, answer())
    assert (result["decision"], result["age_restricted"], result["validation_status"]) == ("restrict", True, "validated")
    assert result["findings"][0]["harm_window"] == "00:00:02 to 00:00:05"
    assert result["findings"][0]["evidence"]["file"] == "frames/t0004s.jpg"


def test_transcript_evidence_shows_the_line(pack):
    result = decide(pack, answer(findings=[{**FINDING, "evidence_frame": None, "evidence_transcript_line": 1}]))
    assert result["findings"][0]["evidence"] == {"type": "transcript", "text": "Look out.", "time": "00:01.20 to 00:04.86"}


def test_hhmmss():
    assert (ud.hhmmss(42), ud.hhmmss(3725)) == ("00:00:42", "01:02:05")


def test_failed_check_is_routed(pack):
    assert_routed_without_a_label(decide(pack, BAD))


def test_human_review_answer_is_routed(pack):
    assert_routed_without_a_label(decide(pack, answer("human_review", "NONE", [])))


def test_remove_on_a_news_report_is_routed_but_not_on_other_clips(pack):
    assert_routed_without_a_label(decide(pack, REMOVE, news=True))
    assert decide(pack, REMOVE)["decision"] == "remove"


def test_news_flag_is_not_sent_to_gemini_and_remove_is_not_retried(pack):
    fake = FakeGemini(REMOVE)
    ud.decide_pack(fake, "test-model", pack, True)
    assert len(fake.prompts) == ud.RUNS_PER_CLIP
    text = " ".join(p.text for p in fake.prompts[0][0].parts if p.text)
    assert "is_news_report" not in text


# --- the page ---

@pytest.fixture(scope="session")
def video(tmp_path_factory):
    path = tmp_path_factory.mktemp("video") / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=10:size=160x90:rate=10", str(path)], check=True)
    return path.read_bytes()


def post(tmp_path, video, *replies, name="clip.mp4", title="A <i>clip</i>", news=False):
    deps = {"client": FakeGemini(*replies), "model_id": "test-model", "whisper": None, "project": "p", "langsmith": None}
    page = create_app(deps, tmp_path).test_client()
    form = {"clip": (io.BytesIO(video), name), "title": title, **({"is_news_report": "on"} if news else {})}
    return page, page.post("/uploads", data=form)


def finished(page, response):
    for _ in range(200):
        if page.get(response.location + "/status").json["done"]:
            return page.get(response.location).text
        time.sleep(0.05)
    raise AssertionError("never finished")


def test_page_shows_the_decision_and_findings(tmp_path, video):
    html = finished(*post(tmp_path, video, answer()))
    for text in (">restrict<", "Age restricted", "00:00:02 to 00:00:05", "VIO-04", "validated", "/frames/t0004s.jpg"):
        assert text in html
    assert "<b>is</b>" not in html and "<i>clip</i>" not in html  # uploader and model text is escaped


@pytest.mark.parametrize("replies, news", [([BAD], False), ([REMOVE], True)])
def test_page_shows_no_label_when_routed(tmp_path, video, replies, news):
    page, response = post(tmp_path, video, *replies, news=news)
    html = finished(page, response)
    body = html.split("<main>")[1].lower()
    assert "routed_to_human_review" in body
    assert ">remove<" not in body and ">restrict<" not in body and ">allow<" not in body and "age restricted" not in body
    queue = page.get("/").text.split("Recent uploads")[0]
    assert "A &lt;i&gt;clip" in queue and "routed_to_human_review" in queue


def test_page_says_it_is_working(tmp_path, video, monkeypatch):
    monkeypatch.setattr("upload_page.decide_upload", lambda *a, **k: time.sleep(0.5) or 1 / 0)
    page, response = post(tmp_path, video, answer())
    assert "Still working" in page.get(response.location).text
    assert "could not be processed" in finished(page, response)  # and a crash is routed, not labelled


@pytest.mark.parametrize("name, title, body", [("notes.txt", "t", None), ("clip.mp4", " ", None), ("clip.mp4", "t", b"not a video")])
def test_bad_uploads_are_refused(tmp_path, video, name, title, body):
    _, response = post(tmp_path, body or video, answer(), name=name, title=title)
    assert response.status_code == 400 and not list(tmp_path.iterdir())


def test_unknown_upload_is_404(tmp_path):
    page = create_app({}, tmp_path).test_client()
    assert page.get("/uploads/../../.env").status_code == 404
    assert page.get("/uploads/" + "0" * 32).status_code == 404


# --- the reviewer's final call ---

def call(page, location, decision="restrict", reviewer="Lena", note="", **headers):
    return page.post(location + "/final_call", data={"decision": decision, "reviewer": reviewer, "note": note}, headers=headers)


def saved(tmp_path):
    return json.loads(next(tmp_path.glob("*/job.json")).read_text())


def test_confirming_is_saved_next_to_the_model_answer(tmp_path, video):
    page, response = post(tmp_path, video, answer())
    finished(page, response)
    assert call(page, response.location).status_code == 303
    job = saved(tmp_path)
    final = job["final_calls"][-1]
    assert (final["decision"], final["model_decision"], final["agrees_with_model"]) == ("restrict", "restrict", True)
    assert "langsmith_trace_url" in final and job["result"]["decision"] == "restrict"
    assert "confirms the model" in page.get(response.location).text
    assert "confirmed" in page.get("/").text


def test_changing_needs_a_note_and_keeps_the_model_answer_and_history(tmp_path, video):
    page, response = post(tmp_path, video, answer())
    finished(page, response)
    refused = call(page, response.location, "remove", "Lena <b>O</b>")
    assert refused.status_code == 400 and "Say why" in refused.text and "final_calls" not in saved(tmp_path)
    assert "<b>O</b>" not in refused.text
    call(page, response.location, "remove", note="Second kick.")
    call(page, response.location, "restrict")
    job = saved(tmp_path)
    assert [c["decision"] for c in job["final_calls"]] == ["remove", "restrict"]
    assert job["final_calls"][0]["agrees_with_model"] is False and job["result"]["decision"] == "restrict"


@pytest.mark.parametrize("decision, reviewer", [("flag", "Lena"), ("", "Lena"), ("restrict", "  ")])
def test_bad_final_calls_are_refused(tmp_path, video, decision, reviewer):
    page, response = post(tmp_path, video, answer())
    finished(page, response)
    assert call(page, response.location, decision, reviewer).status_code == 400


def test_final_call_on_a_routed_clip_shows_no_label_on_its_page(tmp_path, video):
    page, response = post(tmp_path, video, BAD)
    body = finished(page, response).split("<main>")[1].lower()
    assert "make the final call" in body and 'value="remove"' not in body
    assert call(page, response.location, "remove", note="Watched it.").location.endswith("/review#final-call")
    assert saved(tmp_path)["final_calls"][0]["agrees_with_model"] is None
    body = page.get(response.location).text.split("<main>")[1].lower()
    assert "a reviewer has made the final call" in body and "remove" not in body
    assert "Nothing is waiting" in page.get("/").text


def test_final_call_before_the_result_or_from_another_site_is_refused(tmp_path, video, monkeypatch):
    page, response = post(tmp_path, video, answer())
    finished(page, response)
    assert call(page, response.location, **{"Sec-Fetch-Site": "cross-site"}).status_code == 403
    monkeypatch.setattr("upload_page.decide_upload", lambda *a, **k: time.sleep(0.4) or 1 / 0)
    second = page.post("/uploads", data={"clip": (io.BytesIO(video), "c.mp4"), "title": "t"})
    assert call(page, second.location).status_code == 409
    finished(page, second)


def test_news_safety_net_is_named(pack):
    assert decide(pack, REMOVE, news=True)["routed_cause"] == "news_safety_net"
    assert decide(pack, BAD)["routed_cause"] == "failed_check"
    assert decide(pack, answer())["routed_cause"] is None


def test_final_call_goes_to_the_trace_without_names():
    import tracing
    sent = []
    client = SimpleNamespace(create_feedback=lambda *a, **k: sent.append((a, k)))
    assert tracing.save_final_call(client, "trace-1", "remove", False)
    assert sent == [(("trace-1",), {"key": "reviewer_final_call", "value": "remove", "score": 0})]
    assert not tracing.save_final_call(None, "trace-1", "remove", False)
