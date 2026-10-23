# 🎓 Voice Study Buddy

**A voice-first study coach built as an MCP server (Streamable HTTP).**
Built for the **Amazon Developer Hackathon, Alexa+ track**, with an **Open Source** contribution.

> Quiz yourself by voice. Study Buddy tracks what you forget.

**Demo video:** _add your YouTube link here_

---

## What it does

You say *"quiz me on MySQL"*. Study Buddy asks one question at a time, listens to your
answer, tells you if you were right, and uses spaced repetition so the cards you forget
come back sooner. It also shows which topics are weak, and keeps a daily streak.

- **Flashcards:** add them by hand, generate them from pasted notes, an uploaded **PDF**, `.txt` or `.md` file, or let Gemini write them from just a topic.
- **Smart grading:** Gemini judges the *meaning* of your answer, so "a unique ID for every row" can still be correct. Without an API key it falls back to keyword matching.
- **Spaced repetition:** a Leitner box system. Right answers move a card to a later box (reviewed after longer gaps); wrong answers send it back to box 1.
- **Hints and explanations:** ask for a hint (never gives the answer away) or an explanation after answering.
- **Progress:** accuracy per topic, cards due, cards mastered, a streak, and a 7-day activity chart.
- **Voice-ready replies:** every tool returns a short `speech` field written to be read aloud.

## How it works

```
Browser (simulated Alexa+ page)          MCP server (server.py)
  mic / typing  ──►  intent rules  ──►   POST /mcp  (Streamable HTTP, JSON-RPC)
  speech out    ◄──  `speech` field ◄──  tools ──► data.json  +  Gemini API (optional)
```

The simulated Alexa+ page (`alexa_sim.html`) is served by the same server and calls the
MCP tools exactly as an agent would. Its **MCP tool calls** panel shows every call and
its result, including whether Gemini or the keyword matcher graded an answer.

## MCP tools

| Tool | What it does |
|---|---|
| `generate_flashcards` | Create flashcards with Gemini, from notes or from a topic alone |
| `add_flashcard` | Add one card by hand |
| `get_question` | Next question; due cards first, weak cards more often |
| `check_answer` | Grade the answer (Gemini, keyword fallback) and reschedule the card |
| `get_hint` | A hint that does not reveal the full answer |
| `explain_answer` | Short spoken explanation of a card's answer |
| `list_topics` | Topics with card and due counts |
| `weak_topics` | Accuracy per topic, weakest first |
| `study_summary` | Totals, accuracy, streak, and the last 7 days |

An **Agent Skill** that teaches an AI agent how to run a study session with these tools is in
[`skills/study-buddy/SKILL.md`](skills/study-buddy/SKILL.md).

## Quick start

Requires **Python 3.10+** and **Chrome** (for voice input).

```powershell
# Windows PowerShell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed_mysql.py        # optional: loads 10 sample MySQL cards
python server.py
```

```bash
# macOS / Linux
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed_mysql.py
python server.py
```

Then open **http://localhost:8000** in Chrome.

- **MCP endpoint:** `http://localhost:8000/mcp`
- Try saying or typing: `quiz me on mysql`, `hint`, `skip`, `explain`, `how am I doing`, `weak topics`, `stop`.

### Gemini (optional)

Needed only for AI grading, explanations, and flashcard generation. Everything else works without it.

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/).
2. Copy `.env.example` to `.env` and paste your key after `GEMINI_API_KEY=`.
3. Check it: `python check_gemini.py`

`.env` is git-ignored. **Never commit your key.** The default model is `gemini-3.1-flash-lite`;
change it with `GEMINI_MODEL` in `.env`.

## Tests

```
pip install pytest
pytest
```

12 tests cover grading, hints, spaced repetition, streaks, topics, and flashcard generation
(Gemini is stubbed, so no key is needed). `python test_client.py` calls every tool against a
running server over real MCP.

## Project layout

| Path | Purpose |
|---|---|
| `server.py` | The MCP server and all tools |
| `alexa_sim.html` | Simulated Alexa+ web page (voice in, speech out, tool-call log) |
| `skills/study-buddy/SKILL.md` | Agent Skill for the tools |
| `seed_mysql.py` | Loads 10 sample MySQL flashcards |
| `samples/mysql_notes.pdf` | Sample class notes to try the PDF upload |
| `check_gemini.py` | Checks your Gemini key and model |
| `test_client.py` | Calls every tool over MCP |
| `tests/` | Automated tests (pytest) |

## Notes and limitations

- The Alexa+ experience is **simulated** in the browser; it is not running on a real Alexa device.
- Voice input uses the browser's speech recognition (Chrome, needs internet).
- PDF upload reads text PDFs only (first 30 pages, 10 MB); scanned image PDFs are not supported.
- Progress is stored in a local `data.json` for a single user.
- Cards Gemini writes from a topic alone can contain mistakes; pasted notes give more reliable cards.
- The server listens on `127.0.0.1` only.
- The MCP SDK is pinned to `mcp<2`, because SDK 2.x renamed `FastMCP` and changes the API this code uses.

## What's next

- Multiple users, each with their own cards and progress
- PowerPoint uploads and scanned-PDF support (OCR)
- Adaptive review timing based on each card's difficulty
- Exam-date study plans
- Shared decks for classmates
- Connecting to a real Alexa+ device when custom integrations are available

## Built during the hackathon

All code in this repository was written during the hackathon window. It was developed with
AI assistance (Claude) for code generation and debugging, with the idea, direction, testing,
and decisions by the author.

## License

[MIT](LICENSE)