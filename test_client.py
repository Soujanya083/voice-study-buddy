"""Quick check that the Study Buddy server works. Run while server.py is running."""
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://localhost:8000/mcp"


async def main():
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Tools:", [t.name for t in tools.tools])

            async def call(name, args):
                result = await session.call_tool(name, args)
                print(f"\n{name} ->", result.content[0].text)
                return result

            await call("add_flashcard", {
                "topic": "DBMS", "question": "What is a primary key?",
                "answer": "A unique identifier for each row"})
            q = await call("get_question", {"topic": "DBMS"})
            await call("check_answer", {"card_id": 1,
                                        "user_answer": "a unique identifier for rows"})
            await call("weak_topics", {})
            await call("study_summary", {})


asyncio.run(main())
