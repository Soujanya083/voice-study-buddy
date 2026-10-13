"""Voice Study Buddy - an MCP server (Streamable HTTP) for Alexa+ style voice study.

Tools:
  generate_flashcards - turn pasted notes into flashcards (Gemini API)
  add_flashcard       - add one flashcard by hand
  get_question        - next question (spaced repetition: due cards first)
  check_answer        - grade the answer, move the card between Leitner boxes
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

DATA_FILE = Path(os.getenv("STUDY_DATA_FILE", "data.json"))
mcp = FastMCP("Study Buddy", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

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
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
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


@mcp.tool()
def check_answer(card_id: int, user_answer: str) -> dict:
    """Grade the spoken answer (keyword match), then reschedule the card."""
    data = load()
    for card in data["cards"]:
        if card["id"] != card_id:
            continue
        keywords = {w.strip(".,!?").lower() for w in card["answer"].split() if len(w) > 3}
        spoken = user_answer.lower()
        hits = sum(1 for w in keywords if w in spoken)
        ok = bool(keywords) and hits / len(keywords) >= 0.5
        card["correct" if ok else "wrong"] += 1
        card["box"] = min(card["box"] + 1, 5) if ok else 1
        card["due"] = (now() + INTERVALS[card["box"]]).isoformat()
        save(data)
        speech = ("Correct! " if ok else "Not quite. ") + f"The answer is: {card['answer']}"
        return {"correct": ok, "expected_answer": card["answer"],
                "new_box": card["box"], "speech": speech}
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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")  # serves at http://localhost:8000/mcp
