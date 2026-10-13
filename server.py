"""Voice Study Buddy - an MCP server (Streamable HTTP) for Alexa+ style voice study.

Tools:
  generate_flashcards - turn pasted notes into flashcards (Gemini API)
  add_flashcard       - add one flashcard by hand
  get_question        - next question (spaced repetition: due cards first)
  check_answer        - grade the answer (Gemini if available, else keywords), reschedule
  get_hint            - a hint that never gives the full answer away
  explain_answer      - short spoken explanation of a card's answer
  weak_topics         - analytics: accuracy per topic, weakest first
  study_summary       - progress snapshot with a spoken summary

Every response includes a short 'speech' field written to be read aloud.
"""
import json
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse

DATA_FILE = Path(os.getenv("STUDY_DATA_FILE", "data.json"))
mcp = FastMCP("Study Buddy", host=os.getenv("HOST", "127.0.0.1"),
              port=int(os.getenv("PORT", "8000")),
              json_response=True, stateless_http=True)

# Leitner boxes: a correct answer moves a card up and delays its next review.
INTERVALS = {1: timedelta(0), 2: timedelta(days=1), 3: timedelta(days=3),
             4: timedelta(days=7), 5: timedelta(days=14)}


def now() -> datetime:
    return datetime.now(timezone.utc)


def load() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {"cards": []}


def save(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2))


def _new_card(data: dict, topic: str, question: str, answer: str) -> dict:
    card = {"id": max([c["id"] for c in data["cards"]], default=0) + 1,
            "topic": topic.strip().lower(), "question": question.strip(),
            "answer": answer.strip(), "box": 1, "due": now().isoformat(),
            "correct": 0, "wrong": 0}
    data["cards"].append(card)
    return card


def _gemini_text(prompt: str) -> str:
    """Call the Gemini API. Needs GEMINI_API_KEY (free key from Google AI Studio)."""
    from google import genai

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        contents=prompt,
    )
    return resp.text


@mcp.tool()
def generate_flashcards(topic: str, notes: str, count: int = 5) -> dict:
    """Create flashcards from pasted study notes using the Gemini API."""
    count = max(1, min(count, 10))
    prompt = (
        f"From the notes below, write {count} short flashcards. Answers must be "
        "one short sentence, easy to say aloud. Reply with ONLY a JSON array of "
        'objects like [{"question": "...", "answer": "..."}].\n\nNOTES:\n' + notes[:6000]
    )
    try:
        raw = _gemini_text(prompt)
        cards = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
    except Exception as exc:  # no API key, quota hit, bad JSON...
        return {"error": f"Gemini generation failed: {exc}",
                "speech": "Sorry, I could not generate cards right now."}
    data = load()
    added = [_new_card(data, topic, c["question"], c["answer"]) for c in cards[:count]]
    save(data)
    return {"added": len(added), "topic": topic.lower(),
            "speech": f"Done. I added {len(added)} flashcards on {topic}. Ready to be quizzed?"}


@mcp.tool()
def add_flashcard(topic: str, question: str, answer: str) -> dict:
    """Add one flashcard by hand."""
    data = load()
    card = _new_card(data, topic, question, answer)
    save(data)
    return {"card_id": card["id"], "speech": f"Saved. Card {card['id']} added to {topic}."}


@mcp.tool()
def get_question(topic: str = "") -> dict:
    """Get the next question. Cards that are due come first, weak ones more often."""
    cards = [c for c in load()["cards"] if not topic or c["topic"] == topic.lower()]
    if not cards:
        return {"speech": "You have no flashcards yet. Give me some notes to start."}
    due = [c for c in cards if datetime.fromisoformat(c["due"]) <= now()]
    if not due:
        return {"speech": "Nothing is due right now. Nice work, come back later."}
    card = random.choices(due, weights=[1 + c["wrong"] for c in due], k=1)[0]
    return {"card_id": card["id"], "topic": card["topic"], "question": card["question"],
            "speech": f"{card['topic']}. {card['question']}"}


def _grade_with_gemini(question: str, expected: str, given: str):
    """Ask Gemini to judge meaning. Returns (is_correct, short_feedback)."""
    prompt = (
        "You are a friendly tutor grading a spoken answer. Judge the MEANING, not exact "
        "wording. Ignore speech-to-text mistakes.\n"
        f"Question: {question}\nCorrect answer: {expected}\nStudent answer: {given}\n"
        'Reply with ONLY JSON: {"correct": true or false, "feedback": "max 12 words"}'
    )
    raw = _gemini_text(prompt)
    obj = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    return bool(obj["correct"]), str(obj.get("feedback", "")).strip()


def _grade_with_keywords(expected: str, given: str) -> bool:
    keywords = {w.strip(".,!?").lower() for w in expected.split() if len(w) > 3}
    hits = sum(1 for w in keywords if w in given.lower())
    return bool(keywords) and hits / len(keywords) >= 0.5


@mcp.tool()
def check_answer(card_id: int, user_answer: str) -> dict:
    """Grade the spoken answer, then reschedule the card.

    Uses Gemini to judge meaning when GEMINI_API_KEY is set; otherwise (or if
    the call fails) falls back to simple keyword matching.
    """
    data = load()
    for card in data["cards"]:
        if card["id"] != card_id:
            continue
        feedback, graded_by, gemini_error = "", "keywords", None
        try:
            if not os.getenv("GEMINI_API_KEY"):
                raise RuntimeError("no key")
            ok, feedback = _grade_with_gemini(card["question"], card["answer"], user_answer)
            graded_by = "gemini"
        except Exception as exc:
            ok = _grade_with_keywords(card["answer"], user_answer)
            if os.getenv("GEMINI_API_KEY"):
                gemini_error = str(exc)[:200]
        card["correct" if ok else "wrong"] += 1
        card["box"] = min(card["box"] + 1, 5) if ok else 1
        card["due"] = (now() + INTERVALS[card["box"]]).isoformat()
        save(data)
        speech = ("Correct! " if ok else "Not quite. ")
        speech += (feedback + " " if feedback else "") + f"The answer is: {card['answer']}"
        return {"correct": ok, "expected_answer": card["answer"], "new_box": card["box"],
                "graded_by": graded_by, "gemini_error": gemini_error,
                "speech": speech}
    return {"error": f"Card {card_id} not found.", "speech": "I could not find that card."}


@mcp.tool()
def get_hint(card_id: int) -> dict:
    """Give a hint for a card without revealing the whole answer."""
    for card in load()["cards"]:
        if card["id"] == card_id:
            words = card["answer"].split()
            if len(words) > 1:
                hint = " ".join([words[0]] + ["_" * len(w) for w in words[1:]])
                speech = f"Hint: it starts with {words[0]}, and has {len(words)} words."
            else:
                hint = words[0][0] + "_" * (len(words[0]) - 1)
                speech = f"Hint: it starts with the letter {words[0][0]} and has {len(words[0])} letters."
            return {"hint": hint, "speech": speech}
    return {"error": f"Card {card_id} not found.", "speech": "I could not find that card."}


@mcp.tool()
def explain_answer(card_id: int) -> dict:
    """Explain a card's answer in two short sentences (Gemini if available)."""
    for card in load()["cards"]:
        if card["id"] == card_id:
            prompt = (f"Question: {card['question']}\nCorrect answer: {card['answer']}\n"
                      "Explain this to a student in two short sentences, simple words, "
                      "easy to say aloud. No markdown.")
            try:
                if not os.getenv("GEMINI_API_KEY"):
                    raise RuntimeError("no key")
                text = _gemini_text(prompt).strip()
            except Exception:
                text = f"The correct answer is: {card['answer']}"
            return {"explanation": text, "speech": f"About {card['question']} {text}"}
    return {"error": f"Card {card_id} not found.", "speech": "I could not find that card."}


@mcp.tool()
def weak_topics() -> dict:
    """Accuracy per topic, weakest first."""
    stats: dict = {}
    for c in load()["cards"]:
        s = stats.setdefault(c["topic"], {"correct": 0, "wrong": 0})
        s["correct"] += c["correct"]
        s["wrong"] += c["wrong"]
    rows = []
    for topic, s in stats.items():
        total = s["correct"] + s["wrong"]
        rows.append({"topic": topic, "attempts": total,
                     "accuracy_pct": round(100 * s["correct"] / total) if total else None})
    rows.sort(key=lambda r: (r["accuracy_pct"] is None, r["accuracy_pct"] or 0))
    attempted = [r for r in rows if r["accuracy_pct"] is not None]
    speech = (f"Your weakest topic is {attempted[0]['topic']} at "
              f"{attempted[0]['accuracy_pct']} percent." if attempted
              else "You have not answered any questions yet.")
    return {"topics": rows, "speech": speech}


@mcp.tool()
def study_summary() -> dict:
    """Overall progress snapshot."""
    cards = load()["cards"]
    due = sum(1 for c in cards if datetime.fromisoformat(c["due"]) <= now())
    mastered = sum(1 for c in cards if c["box"] >= 4)
    right, wrong = sum(c["correct"] for c in cards), sum(c["wrong"] for c in cards)
    acc = round(100 * right / (right + wrong)) if right + wrong else None
    return {"total_cards": len(cards), "due_now": due, "mastered": mastered,
            "accuracy_pct": acc,
            "speech": f"You have {len(cards)} cards, {due} due now, and {mastered} mastered."}


@mcp.custom_route("/", methods=["GET"])
async def home(request: Request) -> HTMLResponse:
    """Serve the simulated Alexa+ page from the same origin as /mcp."""
    page = Path(__file__).with_name("alexa_sim.html")
    return HTMLResponse(page.read_text(encoding="utf-8"))


if __name__ == "__main__":
    mcp.run(transport="streamable-http")  # MCP: http://localhost:8000/mcp  |  Alexa+ simulator: http://localhost:8000