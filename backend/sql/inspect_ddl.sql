-- Loader : step 1 — extraction of structural schema metadata in ONE bulk query.
-- Single source of truth: backend/src/loader.py reads this file.
-- (SQLAlchemy syntax: :schema_name is a bind param.)
SELECT
    c.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable,
    pg_catalog.col_description(format('%I.%I', c.table_schema, c.table_name)::regclass::oid, c.ordinal_position) AS column_comment,
    CASE WHEN pk.column_name IS NOT NULL THEN TRUE ELSE FALSE END AS is_primary_key,
    fk.target_table,
    fk.target_column,
    -- Planner row-count estimate; NULL when the table was never analyzed (reltuples = -1)
    CASE WHEN pc.reltuples >= 0 THEN pc.reltuples::bigint END AS estimated_row_count
FROM information_schema.columns c
-- Real tables only: information_schema.columns also lists VIEWs and foreign tables
JOIN information_schema.tables t
  ON t.table_schema = c.table_schema AND t.table_name = c.table_name
 AND t.table_type = 'BASE TABLE'
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
-- Row counts: 1:1 join, relnamespace + relname is unique in pg_class
LEFT JOIN pg_namespace pn ON pn.nspname = c.table_schema
LEFT JOIN pg_class pc ON pc.relnamespace = pn.oid AND pc.relname = c.table_name AND pc.relkind = 'r'
WHERE c.table_schema = :schema_name
ORDER BY c.table_name, c.ordinal_position;