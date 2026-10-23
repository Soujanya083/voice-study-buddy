import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_FILE", tmp_path / "data.json")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def add(topic="mysql", q="What is a primary key?", a="A unique identifier for each row"):
    return server.add_flashcard(topic, q, a)["card_id"]


def test_add_and_get_question():
    cid = add()
    q = server.get_question("MySQL")
    assert q["card_id"] == cid and "primary key" in q["question"]


def test_correct_answer_moves_card_up_a_box():
    cid = add()
    r = server.check_answer(cid, "a unique identifier")
    assert r["correct"] and r["new_box"] == 2 and r["graded_by"] == "keywords"


def test_wrong_answer_resets_to_box_1():
    cid = add()
    server.check_answer(cid, "a unique identifier")
    r = server.check_answer(cid, "banana")
    assert not r["correct"] and r["new_box"] == 1


def test_hint_does_not_reveal_answer():
    cid = add()
    assert "identifier" not in server.get_hint(cid)["speech"]


def test_weak_topics_weakest_first():
    a, b = add("good"), add("bad")
    server.check_answer(a, "a unique identifier")
    server.check_answer(b, "banana")
    assert server.weak_topics()["topics"][0]["topic"] == "bad"


def test_list_topics_counts_cards_and_due():
    add("a"), add("a"), add("b")
    rows = {r["topic"]: r for r in server.list_topics()["topics"]}
    assert rows["a"]["cards"] == 2 and rows["b"]["due"] == 1


def _set_activity(days_ago):
    data = server.load()
    data["activity"] = {(date.today() - timedelta(days=d)).isoformat():
                        {"answered": 3, "correct": 2} for d in days_ago}
    server.save(data)


def test_streak_counts_consecutive_days():
    _set_activity([0, 1, 2])
    assert server.study_summary()["streak"] == 3


def test_streak_survives_until_today_is_studied():
    _set_activity([1, 2])
    assert server.study_summary()["streak"] == 2


def test_streak_breaks_after_a_gap():
    _set_activity([0, 2])
    assert server.study_summary()["streak"] == 1


def test_answering_logs_activity_for_today():
    cid = add()
    server.check_answer(cid, "a unique identifier")
    assert server.study_summary()["last7"][-1]["answered"] == 1


def test_generate_flashcards_without_key_fails_politely():
    assert "error" in server.generate_flashcards("x", "notes")


def test_generate_flashcards_with_stubbed_gemini(monkeypatch):
    monkeypatch.setattr(server, "_gemini_text", lambda p: json.dumps(
        [{"question": "Q1?", "answer": "A1"}, {"question": "Q2?", "answer": "A2"}]))
    assert server.generate_flashcards("topic", "", 2)["added"] == 2


# ---- PDF upload ----
def make_pdf(text: str) -> bytes:
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>",
            None,
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET"
    objs[3] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"
    out, offsets = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return out.encode()


def test_pdf_text_is_extracted():
    assert "primary key" in server._pdf_text(make_pdf("A primary key is unique"))


def test_extract_route_returns_text_and_rejects_bad_input():
    from starlette.testclient import TestClient

    client = TestClient(server.mcp.streamable_http_app())
    ok = client.post("/api/extract", content=make_pdf("Indexes speed up reads"))
    assert ok.status_code == 200 and "Indexes" in ok.json()["text"]
    assert client.post("/api/extract", content=b"").status_code == 400
    assert client.post("/api/extract", content=b"not a pdf").status_code == 400


def test_retries_when_gemini_is_busy(monkeypatch):
    monkeypatch.setattr(server.time, "sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("503 UNAVAILABLE high demand")
        return "ok"

    assert server._with_retries(flaky) == "ok" and len(calls) == 3


def test_no_retry_for_other_errors(monkeypatch):
    monkeypatch.setattr(server.time, "sleep", lambda s: None)
    calls = []

    def bad():
        calls.append(1)
        raise RuntimeError("400 invalid API key")

    with pytest.raises(RuntimeError):
        server._with_retries(bad)
    assert len(calls) == 1


# ---- exam planner ----
def add_many(topic, n):
    for i in range(n):
        server.add_flashcard(topic, f"Question {i}?", f"Answer number {i}")


def test_plan_sets_daily_target_from_days_left():
    add_many("mysql", 10)
    p = server.plan_revision(days_left=5)
    assert p["needs_work"] == 10 and p["reviews_per_day"] == 4  # 20 reviews over 5 days
    assert len(p["schedule"]) == 5 and p["days_left"] == 5


def test_plan_accepts_dates_and_remembers_them():
    add_many("mysql", 4)
    exam = date.today() + timedelta(days=3)
    assert server.plan_revision(exam_date=exam.strftime("%d-%m-%Y"))["days_left"] == 3
    assert server.plan_revision()["days_left"] == 3  # remembered
    assert server.study_summary()["exam_in_days"] == 3


def test_plan_needs_a_date_and_rejects_past_dates():
    add_many("mysql", 2)
    assert "error" in server.plan_revision()
    past = (date.today() - timedelta(days=2)).isoformat()
    assert "error" in server.plan_revision(exam_date=past)
    assert "error" in server.plan_revision(exam_date="not a date")


def test_plan_focuses_on_weakest_topic_first():
    good, bad = add("good"), add("bad")
    server.check_answer(good, "a unique identifier")
    server.check_answer(bad, "banana")
    assert server.plan_revision(days_left=4)["focus_topics"][0]["topic"] == "bad"


def test_plan_for_exam_today_is_one_study_day():
    add_many("mysql", 3)
    p = server.plan_revision(exam_date=date.today().isoformat())
    assert p["days_left"] == 0 and p["reviews_per_day"] == 6 and len(p["schedule"]) == 1


def test_plan_without_cards_is_polite():
    assert "error" in server.plan_revision(days_left=5)


def test_far_exam_shows_only_a_week_and_counts_the_rest():
    add_many("mysql", 4)
    p = server.plan_revision(days_left=30)
    assert len(p["schedule"]) == 7 and p["more_days"] == 23
    assert p["schedule"][0]["label"] == "Today" and p["schedule"][1]["label"] == "Tomorrow"


def test_plan_speech_uses_correct_singular():
    add_many("mysql", 2)
    assert "1 review a day" in server.plan_revision(days_left=30)["speech"]