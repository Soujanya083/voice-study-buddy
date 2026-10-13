"""Load 10 sample MySQL flashcards into data.json (run once, then start the server)."""
import json
from datetime import datetime, timezone
from pathlib import Path

CARDS = [
    ("What does SELECT do?", "It retrieves rows from a table"),
    ("What is a primary key?", "A unique identifier for each row"),
    ("What is a foreign key?", "A column that links to the primary key of another table"),
    ("What does the WHERE clause do?", "It filters rows based on a condition"),
    ("What does GROUP BY do?", "It groups rows that share the same values"),
    ("What is an INNER JOIN?", "It returns rows that match in both tables"),
    ("What is the difference between DELETE and TRUNCATE?", "Delete removes selected rows, truncate removes all rows quickly"),
    ("What is an index used for?", "It makes searching and reading data faster"),
    ("What does ORDER BY do?", "It sorts the result by one or more columns"),
    ("What does COUNT return?", "The number of rows"),
]

f = Path("data.json")
data = json.loads(f.read_text()) if f.exists() else {"cards": []}
start = max([c["id"] for c in data["cards"]], default=0)
now = datetime.now(timezone.utc).isoformat()
for i, (q, a) in enumerate(CARDS, start + 1):
    data["cards"].append({"id": i, "topic": "mysql", "question": q, "answer": a,
                          "box": 1, "due": now, "correct": 0, "wrong": 0})
f.write_text(json.dumps(data, indent=2))
print(f"Added {len(CARDS)} MySQL flashcards.")
