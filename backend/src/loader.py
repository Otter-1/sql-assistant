# Loader — extraction et profilage des métadonnées de schéma.
#
# Étape 1 : extraction structurelle (tables, colonnes, PK/FK) en une seule
#           requête bulk (backend/sql/inspect_ddl.sql — source unique).
# Étape 2 : profilage des colonnes (cardinalité, valeurs distinctes,
#           échantillons) pour alimenter l'index de schéma (datamodels.py).
#
# Cible : base PostgreSQL source, configurée via SOURCE_DATABASE_URI (backend/.env).

import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

try:
    from src.queries import cardinality_query, sample_values_query
except ModuleNotFoundError:  # exécution directe en script : python src/loader.py
    from queries import cardinality_query, sample_values_query

# Lecture du fichier SQL pour éviter la dérive entre le fichier et le code
SCHEMA_QUERY_PATH = Path(__file__).resolve().parent.parent / "sql" / "inspect_ddl.sql"

load_dotenv()

_engine = None


def get_engine():
    """Moteur SQLAlchemy lazy, configuré via SOURCE_DATABASE_URI (backend/.env)."""
    global _engine
    if _engine is None:
        uri = os.getenv("SOURCE_DATABASE_URI")
        if not uri:
            raise RuntimeError(
                "SOURCE_DATABASE_URI n'est pas défini — voir backend/.env.example"
            )
        _engine = create_engine(uri)
    return _engine


# step 1: extract the metadata from the database using a single bulk query
def extract_ddl_metadata(schema_name: str = "public") -> Dict[str, Dict[str, Any]]:
    """
    Executes a single bulk SQL query to retrieve all table and column metadata.
    Groups the results into a nested dictionary structure by table name.
    """
    query = SCHEMA_QUERY_PATH.read_text()
    tables_metadata: Dict[str, Dict[str, Any]] = {}
    with get_engine().connect() as connection:
        result = connection.execute(text(query), {"schema_name": schema_name})
        rows = result.mappings().all()
        for row in rows:
            tbl_name = row["table_name"]
            if tbl_name not in tables_metadata:
                tables_metadata[tbl_name] = {
                    "table_name": tbl_name,
                    "schema_name": schema_name,
                    "primary_keys": [],
                    "columns": [],
                }
            is_pk = row["is_primary_key"]
            if is_pk and row["column_name"] not in tables_metadata[tbl_name]["primary_keys"]:
                tables_metadata[tbl_name]["primary_keys"].append(row["column_name"])

            # Une FK est présente si la jointure a trouvé une cible
            is_fk = row["target_table"] is not None
            fk_ref = f"{row['target_table']}.{row['target_column']}" if is_fk else None

            column_metadata = {
                "name": row["column_name"],
                "data_type": row["data_type"],
                "is_primary_key": is_pk,
                "is_foreign_key": is_fk,
                "foreign_key_reference": fk_ref,
                "is_nullable": row["is_nullable"] == "YES",
                "description": row["column_comment"] or "",
            }
            tables_metadata[tbl_name]["columns"].append(column_metadata)
    return tables_metadata


def _is_varchar(data_type: str) -> bool:
    """True pour VARCHAR, VARCHAR(n) et l'équivalent PostgreSQL 'character varying'."""
    dt = data_type.lower()
    return dt.startswith("varchar") or dt.startswith("character varying")


# step 2: profile the columns for cardinality and sample values
def profile_cols(
    tables_metadata: Dict[str, Dict[str, Any]], cardinality_threshold: int = 150
) -> Dict[str, Dict[str, Any]]:
    with get_engine().connect() as connection:
        for table_name, table in tables_metadata.items():
            for column in table["columns"]:
                # Uniquement les chaînes passent par le check de cardinalité
                if _is_varchar(column["data_type"]):
                    results = connection.execute(
                        cardinality_query(table_name, column["name"], cardinality_threshold)
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

                # Pour les autres types, on récupère seulement des échantillons
                # (comportement modifiable plus tard)
                results = connection.execute(
                    sample_values_query(table_name, column["name"], cardinality_threshold)
                ).mappings().first()
                if results is not None:
                    column["sample_values"] = list(results["sample_values"] or [])
    return tables_metadata