---
name: study-buddy
description: Run a spoken study session using the Study Buddy MCP server. Use when the user wants to be quizzed, add or generate flashcards, get hints or explanations, or see which topics they are weak in.
---

# Study Buddy skill

Use the Study Buddy MCP server (Streamable HTTP, `http://localhost:8000/mcp`).
Replies are read aloud, so keep your own wording short and natural. Prefer the
`speech` field in each tool result.

## Workflow

1. **Setup (once).** If the user has notes, call `generate_flashcards(topic, notes)`.
   For single cards use `add_flashcard(topic, question, answer)`.
2. **Quiz loop.**
   - Call `get_question(topic)`. Read the `speech` text. Remember `card_id`.
   - Listen for the user's answer, then call `check_answer(card_id, user_answer)`.
   - Say the result, then call `get_question` again for the next card.
   - If the user asks for help, call `get_hint(card_id)` (never reveal the answer).
   - After an answer, if the user asks "why", call `explain_answer(card_id)`.
   - Stop when the user says stop, skip, or nothing is due.
3. **Review.** Call `study_summary` and `weak_topics`, then suggest the weakest
   topic to practise next.

## Rules
- Ask one question at a time. Never read the answer before the user replies.
- Be encouraging after wrong answers; the card will come back sooner by itself.
- If a tool returns an `error`, say so briefly and suggest the next step.
