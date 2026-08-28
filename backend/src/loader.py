# In progress...
from sqlalchemy import create_engine, text
from typing import Dict, Any, List
import json
from pydantic import BaseModel
BULK_SCHEMA_QUERY = """-- Fetch ALL column structural metadata across the entire schema in ONE query
SELECT 
    c.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable,
    pg_catalog.col_description(format('%I.%I', c.table_schema, c.table_name)::regclass::oid, c.ordinal_position) AS column_comment,
    CASE WHEN pk.column_name IS NOT NULL THEN TRUE ELSE FALSE END AS is_primary_key,
    fk.target_table,
    fk.target_column
FROM information_schema.columns c
-- Join Primary Keys
LEFT JOIN (
    SELECT kcu.table_schema, kcu.table_name, kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu 
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'PRIMARY KEY'
) pk ON c.table_schema = pk.table_schema AND c.table_name = pk.table_name AND c.column_name = pk.column_name
-- Join Foreign Keys
LEFT JOIN (
    SELECT kcu.table_schema, kcu.table_name, kcu.column_name,
           ccu.table_name AS target_table, ccu.column_name AS target_column
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu 
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage ccu 
      ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
) fk ON c.table_schema = fk.table_schema AND c.table_name = fk.table_name AND c.column_name = fk.column_name
WHERE c.table_schema = 'public'
ORDER BY c.table_name, c.ordinal_position;"""

#extract data about cardinality 
VALUE_CARDINALITY_QUERY = """
-- Profile an entire table's string columns in 1 query pass
SELECT 
    COUNT(DISTINCT :column_name) AS distinct_count,
    array_agg(DISTINCT :column_name) FILTER (WHERE :column_name IS NOT NULL) AS distinct_values,
FROM :table_name;
"""
engine = create_engine("postgresql://user:pass@localhost:5432/mydb")

def extract_ddl_metadata(schema_name: str = "public") -> Dict[str, Dict[str, Any]]:
    """
    Executes a single bulk SQL query to retrieve all table and column metadata.
    Groups the results into a nested dictionary structure by table name.
    """
    tables_metadata: Dict[str, Dict[str, Any]] = {}
    with engine.connect() as connection:
        result = connection.execute(text(BULK_SCHEMA_QUERY), {"schema_name":schema_name})
        rows = result.mappings().all()
        for row in rows:
            tbl_name = row["table_name"]
            if tbl_name not in tables_metadata:
                tables_metadata[tbl_name] = {
                    "table_name": tbl_name,
                    "schema_name":schema_name,
                    "primary_keys":[],
                    "columns": []
                }
            if row["is_primary_key"] and row["column_name"] not in tables_metadata["primary_keys"]:
                tables_metadata[tbl_name]["primary_keys"].append(row["column_name"])

            # Form foreign key target string
            fk_ref = None
            if row["is_foreign_key"] and row["target_table"]:
                fk_ref = f"{row['target_table']}.{row['target_column']}"

            column_metadata = {
                "name": row["column_name"],
                "data_type": row["data_type"],
                "is_primary_key": row["is_primary_key"],
                "is_foreign_key": row["is_foreign_key"],
                "foreign_key_reference": fk_ref,
                "is_nullable": row["is_nullable"] =="YES",
                "description": row["column_comment"] or ""

            }
            tables_metadata[tbl_name]["columns"].append(column_metadata)
        return tables_metadata
    

    # Placeholder for extracting DDL metadata from the database
    # This function should connect to the database and extract schema information