from pathlib import Path
from typing import Any

from langchain.agents import create_agent, AgentState
from langchain.tools import tool
from langchain_openrouter import ChatOpenRouter

from langgraph.runtime import Runtime
from langchain.agents.middleware import before_model


from langchain.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES 

import duckdb

model = ChatOpenRouter(
    model="deepseek/deepseek-v4-flash",
    openrouter_provider={"data_collection": "deny"})



@before_model
def trim_memory(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """Keep only the last few messages to fit context window."""
    RECENT_COUNT = 10
    messages = state["messages"]
    tools_used = sum(msg.type == "tool" for msg in messages)
    if len(messages) <= RECENT_COUNT:
        return None  # No changes needed

    first_msg = messages[0]
    recent_messages = messages[-RECENT_COUNT:] if (len(messages)+tools_used) % 2 == 0 else messages[-(RECENT_COUNT + 1):]
    new_messages = [first_msg] + recent_messages

    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *new_messages
        ]
    }

@tool
def query_db(sql: str) -> str:
    """Input to this tool is a detailed and correct SQL query, output is a result from the database.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    If you encounter an issue with Unknown column 'xxxx' in 'field list', use the schemas provided again."""
    with duckdb.connect("demo.db") as con:
        try:
            result = con.execute(sql).df().to_string(index=False)
            return result
        except Exception as e:
            return f"Error occurred: {e}"

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.md"
SCHEMA = SCHEMA_PATH.read_text() if SCHEMA_PATH.exists() else ""

system_prompt = f"""You are a SQL assistant specialized in production and
industrial maintenance data.
You help query a DuckDB database of production and maintenance data.

## Database schema
The complete schema is provided below. Do NOT run SHOW TABLES or DESCRIBE.
Use exactly these table and column names in your queries.

{SCHEMA}

## Rules

1. **Language** — Answer in English.

2. **Queries** — Generate valid DuckDB SQL. Limit to 10 results unless the
   user asks for a specific number. Use ORDER BY to show the most relevant
   results.

3. **Columns** — Only use SELECT * to explore an unknown table. Otherwise,
   query only the relevant columns.

4. **Safety** — NEVER run DML (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE).
   Read-only only.

5. **Errors** — If a query fails, analyze the error, fix the syntax
   and retry. Maximum 3 attempts.

6. **Response format** — Structure your answers as follows:
   - The question asked
   - The SQL query executed (in a code block)
   - The results as figures (no raw table, one concise sentence)
   - The source: which table and how many rows were consulted
   - If applicable, a trend or insight

7. **Precision** — Give exact values with their units
   (hours, tons, etc.). Don't say "approximately".

8. **Columns** — Names are in French or English. Use them as-is.
"""


agent = create_agent(model=model,
                     tools=[query_db],
                     system_prompt=system_prompt,
                     middleware=[trim_memory],
                     )

# ── Title generator ────────────────────────────────────────────────
# Lightweight agent for conversation naming, used via stateless run
# from the frontend after the first message of a new thread.

title_system_prompt = """You generate short titles for conversations.

From the user's first message, generate a title in English
that summarizes the conversation topic.

Rules:
- 3 to 6 words maximum
- In English
- No trailing punctuation
- No quotation marks
- Output NOTHING but the title
- Example: "Handling downtime" instead of "What is the average downtime in handling?"
- The title must be concise and informative"""

title_generator = create_agent(
    model=model,
    system_prompt=title_system_prompt,
)
