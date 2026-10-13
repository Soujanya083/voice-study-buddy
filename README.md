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
| `check_answer` | Grades answer, reschedules card |
| `weak_topics` | Accuracy per topic, weakest first |
| `study_summary` | Total, due, mastered, accuracy |

Every response has a `speech` field written to be read aloud.

## Run
```
pip install -r requirements.txt
python server.py          # http://localhost:8000/mcp
```
Test with: `npx @modelcontextprotocol/inspector` (Streamable HTTP, URL above).

### Gemini (optional, needed for `generate_flashcards`)
Get a free API key from Google AI Studio, then:
```
export GEMINI_API_KEY=your_key_here     # never commit this key
export GEMINI_MODEL=gemini-2.5-flash    # optional, pick any current model
```
Without a key, everything else still works; add cards with `add_flashcard`.

## Built during the hackathon
All of this code was written during the hackathon window. (Edit this line if
you reuse earlier work.)

## License
MIT
