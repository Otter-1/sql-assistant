# Loader — schema metadata extraction and profiling.
#
# Step 1: structural extraction (tables, columns, PK/FK) in ONE bulk
#           query (backend/sql/inspect_ddl.sql — single source of truth).
# Step 2: column profiling (cardinality, distinct values, samples) to
#           feed the schema index (datamodels.py).
# Step 3: LLM table descriptions (src/descriptions.py).
# Step 4: validation as DatabaseSchemaIndex + JSON export.
#
# HOT-SWAPPABLE: the target database URI is passed on every call (no
# environment variable). One run per database — ingest as many databases
# as needed, each into its own JSON file:
#     python src/loader.py --uri postgresql+psycopg://user:pw@host:5432/demo

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

from pydantic import ValidationError

try:
    from src.datamodels import DatabaseSchemaIndex
    from src.queries import cardinality_query, sample_values_query
    from src.descriptions import generate_table_descriptions
except ModuleNotFoundError:  # direct script execution: python src/loader.py
    from queries import cardinality_query, sample_values_query
    from descriptions import generate_table_descriptions
    from datamodels import DatabaseSchemaIndex

# Read the SQL file to avoid drift between the file and the code
SCHEMA_QUERY_PATH = Path(__file__).resolve().parent.parent / "sql" / "inspect_ddl.sql"

# Default output directory, anchored to the loader's location (CWD-independent)
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "db_indexes"

_engines: Dict[str, Any] = {}


def get_engine(database_uri: str):
    """Lazy SQLAlchemy engine, cached per URI — hot-swappable across databases.

    Pass the target database URI on every call; nothing is read from the
    environment. The cache is keyed by URI: re-ingesting the same database
    reuses its connection pool, while a new URI gets a brand-new engine.
    """
    if database_uri not in _engines:
        _engines[database_uri] = create_engine(database_uri)
    return _engines[database_uri]


def derive_database_name(database_uri: str) -> str:
    """Database name from the URI path: postgresql://host/demo -> 'demo'."""
    name = urlparse(database_uri).path.lstrip("/")
    return name or "db"


def derive_engine_name(database_uri: str) -> str:
    """Human-readable engine name from the URI scheme (e.g. postgresql -> PostgreSQL)."""
    scheme = urlparse(database_uri).scheme.split("+")[0]
    return {"postgresql": "PostgreSQL", "duckdb": "DuckDB", "sqlite": "SQLite"}.get(scheme, scheme)


# step 1: extract the metadata from the database using a single bulk query
def extract_ddl_metadata(database_uri: str, schema_name: str = "public") -> List[Dict[str, Any]]:
    """
    Executes a single bulk SQL query to retrieve all table and column metadata.
    Groups the results into a list of table dicts (one entry per table),
    each carrying primary keys, FK relationships and the estimated row count.
    """
    query = SCHEMA_QUERY_PATH.read_text()
    tables_metadata: List[Dict[str, Any]] = []
    tables_index: Dict[str, int] = {}
    with get_engine(database_uri).connect() as connection:
        rows = connection.execute(text(query), {"schema_name": schema_name}).mappings().all()
        for row in rows:
            tbl_name = row["table_name"]
            if tbl_name not in tables_index:
                tables_index[tbl_name] = len(tables_metadata)
                tables_metadata.append({
                    "table_name": tbl_name,
                    "schema_name": schema_name,
                    "estimated_row_count": row["estimated_row_count"],
                    "primary_keys": [],
                    "columns": [],
                    "relationships": [],
                })
            tbl = tables_metadata[tables_index[tbl_name]]

            is_pk = bool(row["is_primary_key"])
            if is_pk and row["column_name"] not in tbl["primary_keys"]:
                tbl["primary_keys"].append(row["column_name"])

            # A FK is present when the join found a target
            is_fk = row["target_table"] is not None
            fk_ref = f"{row['target_table']}.{row['target_column']}" if is_fk else None
            if is_fk:
                tbl["relationships"].append({
                    "foreign_key_column": row["column_name"],
                    "target_table": row["target_table"],
                    "target_column": row["target_column"],
                    # "relationship_type": TODO — infer one-to-many vs many-to-one later
                })

            tbl["columns"].append({
                "name": row["column_name"],
                "data_type": row["data_type"],
                "is_primary_key": is_pk,
                "is_foreign_key": is_fk,
                "foreign_key_reference": fk_ref,
                "is_nullable": row["is_nullable"] == "YES",
                "description": row["column_comment"] or "",
            })
    return tables_metadata


def _is_varchar(data_type: str) -> bool:
    """True for VARCHAR, VARCHAR(n) and the PostgreSQL equivalent 'character varying'."""
    dt = data_type.lower()
    return dt.startswith("varchar") or dt.startswith("character varying")


def _json_safe(value: Any) -> Any:
    """Keep scalar sample values JSON-serializable (str/int/float/bool).

    Dates/timestamps become ISO strings, Decimals become floats — the index
    is exported as JSON, where those types have no native representation.
    """
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


# step 2: profile the columns for cardinality and sample values
def profile_cols(
    tables_metadata: List[Dict[str, Any]],
    database_uri: str,
    cardinality_threshold: int = 150,
) -> List[Dict[str, Any]]:
    with get_engine(database_uri).connect() as connection:
        for table in tables_metadata:
            for column in table["columns"]:
                # Only strings go through the cardinality check
                if _is_varchar(column["data_type"]):
                    results = connection.execute(
                        cardinality_query(table["table_name"], column["name"], cardinality_threshold)
                    ).mappings().first()
                    if results is None:
                        column["is_high_cardinality_string"] = False
                        column["enum_values"] = []
                    elif results["distinct_count"] > cardinality_threshold:
                        column["is_high_cardinality_string"] = True
                        column["sample_values"] = [_json_safe(v) for v in (results["distinct_values"] or [])]
                    else:
                        column["is_high_cardinality_string"] = False
                        column["enum_values"] = [_json_safe(v) for v in (results["distinct_values"] or [])]
                    continue

                # For other types, only fetch samples
                # (behavior can be changed later)
                results = connection.execute(
                    sample_values_query(table["table_name"], column["name"], cardinality_threshold)
                ).mappings().first()
                if results is not None:
                    column["sample_values"] = [_json_safe(v) for v in (results["sample_values"] or [])]
    return tables_metadata

# Step 3: generate table descriptions using the LLM
def add_table_descriptions(tables_metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate concise descriptions for each table using the LLM."""
    return generate_table_descriptions(tables_metadata)


# Step 4: combine all steps into a single function, then validate the result
# against the datamodels.DatabaseSchemaIndex model
def extract_and_profile_schema(
    database_uri: str,
    schema_name: str = "public",
    cardinality_threshold: int = 150,
    db_name: Optional[str] = None,
    engine: Optional[str] = None,
) -> DatabaseSchemaIndex:
    """Extracts the schema metadata, profiles the columns, and generates table descriptions.

    database_uri is the only required argument — call once per database to index
    (hot-swappable). db_name and engine default to values derived from the URI.
    """
    engine = engine or derive_engine_name(database_uri)
    db_name = db_name or derive_database_name(database_uri)
    tables_metadata = extract_ddl_metadata(database_uri, schema_name)
    tables_metadata = profile_cols(tables_metadata, database_uri, cardinality_threshold)
    tables_metadata = add_table_descriptions(tables_metadata)
    unverified_database_index = {
        "engine": engine,
        "database_name": db_name,
        "tables": tables_metadata,
    }
    try:
        # Validate the whole index against the DatabaseSchemaIndex model
        validated_database_index = DatabaseSchemaIndex(**unverified_database_index)
    except ValidationError as e:
        print("Validation error:", e)
        raise

    return validated_database_index

# step 5: save the validated index to a JSON file
def save_index_to_json(
    index: DatabaseSchemaIndex,
    output_name: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """Save the validated DatabaseSchemaIndex to a JSON file.

    Default location: <repo>/backend/db_indexes/<database_name>_schema_index.json,
    anchored to the loader instead of the process CWD. Returns the written path.
    """
    index_json = index.model_dump_json(indent=2)
    output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)
    if output_name is None:
        output_name = f"{index.database_name}_schema_index.json"

    output_path = output_dir / output_name
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(index_json)
    return output_path


def main() -> None:
    """CLI entry point — one run per database (plug-and-play ingestion)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest a source database into the schema index (schema_metadata JSON)."
    )
    parser.add_argument(
        "--uri", required=True,
        help="SQLAlchemy database URI — hot-swappable: one run per database",
    )
    parser.add_argument("--schema", default="public", help="Schema to index (PostgreSQL schemas)")
    parser.add_argument("--db-name", default=None, help="Override the database name derived from the URI")
    parser.add_argument("--engine", default=None, help="Override the engine name derived from the URI")
    parser.add_argument("--cardinality-threshold", type=int, default=150)
    parser.add_argument("--output-dir", default=None, help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--output-name", default=None, help="Output file name (default: <db_name>_schema_index.json)")
    args = parser.parse_args()

    index = extract_and_profile_schema(
        args.uri,
        schema_name=args.schema,
        cardinality_threshold=args.cardinality_threshold,
        db_name=args.db_name,
        engine=args.engine,
    )
    path = save_index_to_json(index, output_name=args.output_name, output_dir=args.output_dir)
    print(f"indexed {len(index.tables)} table(s) from '{index.database_name}' -> {path}")


if __name__ == "__main__":
    main()