# Voice Study Buddy (MCP server)

A voice-first study coach built as an MCP server (Streamable HTTP) for the
Amazon Developer Hackathon, Alexa+ track.

You say: "Quiz me on DBMS." It asks a question out loud, grades your answer,
and uses spaced repetition (Leitner boxes) so weak cards come back sooner.
The Gemini API turns your pasted notes into flashcards. A weak-topics report
shows where to focus.

## Tools
| Tool | What it does |
|---|---|
| `generate_flashcards` | Notes -> flashcards via Gemini API |
| `add_flashcard` | Add a card by hand |
| `get_question` | Next due question (weak cards first) |
| `check_answer` | Grades answer (Gemini judges meaning; keyword fallback), reschedules card |
| `get_hint` | Hint without revealing the answer |
| `explain_answer` | Short spoken explanation |
| `weak_topics` | Accuracy per topic, weakest first |
| `study_summary` | Total, due, mastered, accuracy |

Every response has a `speech` field written to be read aloud.

An Agent Skill for driving these tools is in `skills/study-buddy/SKILL.md`.

## Run
```
pip install -r requirements.txt
python server.py          # http://localhost:8000/mcp
```
Then open **http://localhost:8000** in Chrome for the simulated Alexa+ page
(`alexa_sim.html`). It talks to the MCP server at `/mcp`, uses the browser's
speech recognition for input and speech synthesis to read replies aloud, and
shows a live log of every MCP tool call.

You can also run `python test_client.py` to call every tool from a script.

### Gemini (optional, needed for AI grading and `generate_flashcards`)
1. Get a free API key from Google AI Studio.
2. Copy `.env.example` to `.env` and paste your key after `GEMINI_API_KEY=`.
   The server reads it automatically. `.env` is git-ignored, so never commit it.

Optional: `GEMINI_MODEL` (default `gemini-3.1-flash-lite`). Check your key with
`python check_gemini.py`. Without a key, everything else still works.

## Built during the hackathon
All of this code was written during the hackathon window. (Edit this line if
you reuse earlier work.)

## License
MIT