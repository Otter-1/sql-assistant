# Chroma client factory — one embedded PersistentClient per path, cached.
#
# The entire embedded-vs-server decision lives here. Embedded on-disk is the
# locked choice (docs/internal/ARCHITECTURE_V2.md): one process writes at a
# time, index size is a few thousand entries. If a dedicated Chroma server is
# ever needed (multi-process, remote clients), add a branch here that returns
# chromadb.HttpClient(host, port) — call sites don't change.
#
# Anchored to this file, NOT the CWD, so it behaves the same from `langgraph
# dev`, the loader CLI, or tests:  <repo>/backend/vector_data/
#
# Single-writer constraint: never mount the same path from two live backend
# instances (e.g. `langgraph dev` + a prod container) — PersistentClient takes
# a filesystem lock per path.
#
# Embedding function: not set yet (Chroma's default applies). TODO before
# runtime use: explicit local multilingual sentence-transformers (locked
# decision in docs/internal/ARCHITECTURE_V2.md) — the default all-MiniLM is
# English-only and downloaded from HuggingFace at query time.

from pathlib import Path

import chromadb
from chromadb.api import ClientAPI

try:
    from src.datamodels import SchemaStoreMetadata, ValueStoreMetadata
except ModuleNotFoundError:  # direct script execution
    from datamodels import SchemaStoreMetadata, ValueStoreMetadata

# Default runtime path, anchored to this file (CWD-independent),
# same pattern as loader.DEFAULT_OUTPUT_DIR.
DEFAULT_CHROMA_PATH = Path(__file__).resolve().parent.parent / "vector_data"

# One client per path for the process lifetime.
_engines: dict[str, ClientAPI] = {}

SCHEMA_STORE = "schema_store"
VALUE_STORE = "value_store"


def get_client(path: str | Path | None = None) -> ClientAPI:
    """Lazy, cached PersistentClient per path (hot-swappable, like loader.get_engine).

    Pass a path per call; nothing is read from the environment. The cache is
    keyed by resolved path so one process gets exactly one client per
    directory — required by Chroma's single-writer-per-path constraint.
    """
    resolved = str(Path(path).resolve()) if path else str(DEFAULT_CHROMA_PATH)
    if resolved not in _engines:
        Path(resolved).mkdir(parents=True, exist_ok=True)
        _engines[resolved] = chromadb.PersistentClient(path=resolved)
    return _engines[resolved]


def reset_cache() -> None:
    """Drop cached clients (tests / re-indexing with a fresh directory)."""
    _engines.clear()


def init_store(path: str | Path | None = None) -> None:
    """Create the store collections if missing (idempotent)."""
    client = get_client(path)
    client.get_or_create_collection(name=SCHEMA_STORE)
    client.get_or_create_collection(name=VALUE_STORE)


def _normalize_key(part: str) -> str:
    """Normalize one ID part: case-insensitive, whitespace-trimmed.

    Keeps 'Press P-102' and 'press p-102 ' from the same DB as two entries.
    """
    return part.strip().casefold()


def add_to_schema_store(
    metadata: SchemaStoreMetadata,
    document: str,
    path: str | Path | None = None,
) -> None:
    """Upsert one entry into the schema_store collection.

    Deterministic natural-key ID: kind:db:table[:column]:value — re-running
    ingestion updates the entry instead of duplicating it (add would raise on
    duplicate IDs; upsert makes the loader idempotent).
    """
    client = get_client(path)
    collection = client.get_or_create_collection(name=SCHEMA_STORE)

    parts = [metadata.kind.value, metadata.db, metadata.table]
    if metadata.column:
        parts.append(metadata.column)
    if metadata.value:
        parts.append(metadata.value)
    constructed_id = ":".join(_normalize_key(p) for p in parts)

    collection.upsert(
        ids=constructed_id,
        metadatas=metadata.model_dump(mode="json"),
        documents=document,
    )


def add_to_value_store(
    metadata: ValueStoreMetadata,
    document: str,
    path: str | Path | None = None,
) -> None:
    """Upsert one entry into the value_store collection.

    Deterministic natural-key ID: db:table:column:value (NOT frequency — it
    changes with the data and would duplicate entries on re-profiling).
    """
    client = get_client(path)
    collection = client.get_or_create_collection(name=VALUE_STORE)

    constructed_id = ":".join(
        _normalize_key(p)
        for p in (metadata.db, metadata.table, metadata.column, metadata.value)
    )

    collection.upsert(
        ids=constructed_id,
        metadatas=metadata.model_dump(mode="json"),
        documents=document,
    )
