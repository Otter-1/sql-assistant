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

from pathlib import Path

import chromadb
from chromadb.api import ClientAPI

# Default runtime path, anchored to this file (CWD-independent),
# same pattern as loader.DEFAULT_OUTPUT_DIR.
DEFAULT_CHROMA_PATH = Path(__file__).resolve().parent.parent / "vector_data"

# One client per path for the process lifetime.
_engines: dict[str, ClientAPI] = {}


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
