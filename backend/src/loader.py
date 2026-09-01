# Loader — schema metadata extraction and profiling.
#
# Step 1: structural extraction (tables, columns, PK/FK) in ONE bulk
#           query (backend/sql/inspect_ddl.sql — single source of truth).
# Step 2: column profiling (cardinality, distinct values, samples) to
#           feed the schema index (datamodels.py).
#
# Target: source PostgreSQL database, configured via SOURCE_DATABASE_URI (backend/.env).

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
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

load_dotenv()

_engine = None


def get_engine():
    """Lazy SQLAlchemy engine, configured via SOURCE_DATABASE_URI (backend/.env)."""
    global _engine
    if _engine is None:
        uri = os.getenv("SOURCE_DATABASE_URI")
        if not uri:
            raise RuntimeError(
                "SOURCE_DATABASE_URI is not set — see backend/.env.example"
            )
        _engine = create_engine(uri)
    return _engine



# step 1: extract the metadata from the database using a single bulk query
def extract_ddl_metadata(schema_name: str = "public") -> List[Dict[str, Any]]:
    """
    Executes a single bulk SQL query to retrieve all table and column metadata.
    Groups the results into a list of table dicts (one entry per table),
    each carrying primary keys, FK relationships and the estimated row count.
    """
    query = SCHEMA_QUERY_PATH.read_text()
    tables_metadata: List[Dict[str, Any]] = []
    tables_index: Dict[str, int] = {}
    with get_engine().connect() as connection:
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


# step 2: profile the columns for cardinality and sample values
def profile_cols(
    tables_metadata: List[Dict[str, Any]], cardinality_threshold: int = 150
) -> List[Dict[str, Any]]:
    with get_engine().connect() as connection:
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
                        column["sample_values"] = list(results["distinct_values"] or [])
                    else:
                        column["is_high_cardinality_string"] = False
                        column["enum_values"] = list(results["distinct_values"] or [])
                    continue

                # For other types, only fetch samples
                # (behavior can be changed later)
                results = connection.execute(
                    sample_values_query(table["table_name"], column["name"], cardinality_threshold)
                ).mappings().first()
                if results is not None:
                    column["sample_values"] = list(results["sample_values"] or [])
    return tables_metadata

# Step 3: generate table descriptions using the LLM
def add_table_descriptions(tables_metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate concise descriptions for each table using the LLM."""
    return generate_table_descriptions(tables_metadata)


# Step 4: combine all steps into a single function, then validate the result
# against the datamodels.DatabaseSchemaIndex model
def extract_and_profile_schema(
    schema_name: str = "public",
    cardinality_threshold: int = 150,
    db_name: str = "db",
    engine: str = "PostgreSQL",
) -> DatabaseSchemaIndex:
    """Extracts the schema metadata, profiles the columns, and generates table descriptions."""
    tables_metadata = extract_ddl_metadata(schema_name)
    tables_metadata = profile_cols(tables_metadata, cardinality_threshold)
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