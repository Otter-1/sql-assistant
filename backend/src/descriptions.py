"""Offline table-description generation.

Fills the `description` field of each table dict produced by the loader
(src/loader.py) using an LLM, so the metadata can validate as
`TableMetadata` (datamodels.py declares `description` as required).

Pipeline (offline ingestion step, P1):
    tables_metadata = loader.extract_ddl_metadata()  # list of table dicts
    tables_metadata = loader.profile_cols(tables_metadata)
    generate_table_descriptions(tables_metadata)     # fills table["description"]
    # -> now validatable as List[TableMetadata] and exportable to schema_metadata.json

The agent never sees the DB: it receives one curated "brief" per table
(no description field, no profiling internals) and replies with a single
plain-text description. One LLM call per table, sequential by default.

Idempotent: tables that already carry a non-empty description are skipped,
so a partial failure can be re-run without re-burning tokens. Each call is
retried with exponential backoff.
"""

import time
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openrouter import ChatOpenRouter

DEFAULT_MODEL = "deepseek/deepseek-v4-flash"

# Retry policy for LLM calls (network / provider hiccups)
MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_S = 1.0  # delays: 1s, 2s


# ── Model factory ─────────────────────────────────────────────────────
def get_description_model() -> ChatOpenRouter:
    """Shared model instance for description generation (OpenRouter)."""
    return ChatOpenRouter(model=DEFAULT_MODEL, openrouter_provider={"data_collection": "deny"})


# ── Table brief (the curated, injected context) ───────────────────────
def build_table_brief(table: Dict[str, Any]) -> str:
    """Render one table dict (loader format) as the brief fed to the model.

    Includes what the model needs to describe the table: name, scale guess,
    PKs, FK relationships and the columns (name, type, nullability, DB
    comment, enum/sample values). Deliberately EXCLUDES:
      - `description` (it is the output, not an input)
      - profiling internals (`is_high_cardinality_string`, ...)
      - the loader's column `is_primary_key`/`is_foreign_key` booleans,
        which are redundant with `primary_keys` / `relationships`.
    """
    lines = [f"Table: {table['table_name']}"]
    if table.get("estimated_row_count") is not None:
        lines.append(f"Estimated row count: {table['estimated_row_count']}")
    if table.get("primary_keys"):
        lines.append(f"Primary key(s): {', '.join(table['primary_keys'])}")
    if table.get("relationships"):
        rels = []
        for r in table["relationships"]:
            rels.append(
                f"{r['foreign_key_column']} -> {r['target_table']}.{r['target_column']}"
            )
        lines.append(f"Foreign key(s): {', '.join(rels)}")
    lines.append("Columns:")
    for col in table["columns"]:
        col_line = f"  - {col['name']} ({col['data_type']})"
        nullable = "nullable" if col.get("is_nullable") else "NOT NULL"
        col_line += f" — {nullable}"
        if col.get("description"):
            col_line += f" — {col['description']}"
        if col.get("enum_values"):
            col_line += f" — values: {', '.join(str(v) for v in col['enum_values'])}"
        elif col.get("sample_values"):
            col_line += f" — e.g. {', '.join(str(v) for v in col['sample_values'][:8])}"
        lines.append(col_line)
    return "\n".join(lines)


# ── The description prompt (English, so it aligns with the rest of the port) ──
DESCRIPTION_SYSTEM_PROMPT = """You are a database documentation assistant.

You receive a compact schema extract for ONE table (name, estimated scale, primary and foreign keys, and its columns with types, nullability, database comments and sample/enum values).

Write a SINGLE descriptive paragraph for that table, in English, 40-70 words, that a data analyst could use to decide whether this table answers their question. Follow these rules:

1. Purpose first: what the table represents and, when inferable, why it exists (e.g. a link/junction table, a history/log, a reference/dimension).
2. Content: what notable columns hold, ONCE EACH. Mention dates, statuses, OR metric values if such columns are present — but never invent columns or meanings that are not in the extract. (Values like "north"/"south" are clues, not content.)
3. Joins: only if foreign keys are visible, name the joined tables (e.g. "links to orders").
4. Style: neutral, factual, no hedging ("appears", "likely"). No markdown, no bullets. Start directly with the table's role — never with "This table" or "The table".
5. Never repeat the table name, and never mention row counts or column types (types are visible elsewhere).

Do not output anything except the description sentence."""


def generate_table_descriptions(
    tables_metadata: List[Dict[str, Any]],
    model: Optional[ChatOpenRouter] = None,
    invoke: Optional[Callable[[List[Any]], Any]] = None,
) -> List[Dict[str, Any]]:
    """Fill `description` for every table dict, in place, and return the list.

    Idempotent: tables with a non-empty description are skipped (cheap
    re-runs after a partial failure). Each LLM call is retried with
    exponential backoff (MAX_ATTEMPTS).

    `invoke` is injectable for tests (defaults to `model.invoke([...]).content`
    and constructs the model lazily only when actually needed).
    """
    pending = [t for t in tables_metadata if not str(t.get("description") or "").strip()]
    skipped = len(tables_metadata) - len(pending)
    if skipped:
        print(f"[descriptions] skipping {skipped} table(s) with an existing description")

    if invoke is None:
        invoke = _default_invoke(model)

    for table in pending:
        brief = build_table_brief(table)
        prompt = [
            SystemMessage(content=DESCRIPTION_SYSTEM_PROMPT),
            HumanMessage(content=brief),
        ]
        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                desc = invoke(prompt) or ""
                table["description"] = str(desc).strip()
                break
            except Exception as e:  # network / provider errors
                last_error = e
                if attempt < MAX_ATTEMPTS:
                    time.sleep(RETRY_BASE_DELAY_S * (2 ** (attempt - 1)))
        else:
            raise RuntimeError(
                f"table {table['table_name']!r}: description generation failed "
                f"after {MAX_ATTEMPTS} attempts: {last_error}"
            ) from last_error
    return tables_metadata


def _default_invoke(model: Optional[ChatOpenRouter] = None) -> Callable[[List[Any]], Any]:
    """Default model call: lazily build the model and return a list -> content callable."""
    model = model or get_description_model()
    return lambda messages: model.invoke(messages).content