from sqlalchemy import text


def cardinality_query(table_name: str, column_name: str, cardinality_threshold: int) -> text:
    """Distinct-count + distinct values for one column, up to the threshold.

    Returns distinct_count and an array of up to `cardinality_threshold`
    distinct values (ordered). One query instead of two scans.
    """
    safe_col = f'"{column_name}"'
    safe_table = f'"{table_name}"'
    return text(f"""
    WITH distinct_values AS (
        SELECT DISTINCT {safe_col} AS value
        FROM {safe_table}
        WHERE {safe_col} IS NOT NULL
        ORDER BY {safe_col}
        LIMIT :limit
    )
    SELECT
        (SELECT COUNT(DISTINCT {safe_col}) FROM {safe_table}) AS distinct_count,
        (SELECT array_agg(value ORDER BY value) FROM distinct_values) AS distinct_values
    """).bindparams(limit=cardinality_threshold)


def sample_values_query(table_name: str, column_name: str, sample_size: int) -> text:
    """Sample values for one column, up to `sample_size` rows.

    `sample_size` is a sample size (≈20), NOT the cardinality threshold
    (150) — two different concepts that previously shared one knob.
    """
    safe_col = f'"{column_name}"'
    safe_table = f'"{table_name}"'
    return text(f"""
    SELECT array_agg(value ORDER BY value) AS sample_values
    FROM (
        SELECT {safe_col} AS value
        FROM {safe_table}
        WHERE {safe_col} IS NOT NULL
        ORDER BY {safe_col}
        LIMIT :limit
    ) sub
    """).bindparams(limit=sample_size)
