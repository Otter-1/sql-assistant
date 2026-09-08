from sqlalchemy import text


def cardinality_query(table_name: str, column_name: str, cardinality_threshold: int) -> text:
    """Distinct-count + distinct values + per-value frequencies for one column.

    Returns three aligned columns:
      - distinct_count: full COUNT(DISTINCT) (untruncated)
      - distinct_values: up to `cardinality_threshold` values, ordered
      - frequencies: occurrence counts, same order as distinct_values
    One GROUP BY pass instead of a DISTINCT pass; the count subquery stays
    separate because the value list is truncated at the threshold.
    """
    safe_col = f'"{column_name}"'
    safe_table = f'"{table_name}"'
    return text(f"""
    WITH value_counts AS (
        SELECT {safe_col} AS value, COUNT(*) AS frequency
        FROM {safe_table}
        WHERE {safe_col} IS NOT NULL
        GROUP BY {safe_col}
        ORDER BY value
        LIMIT :limit
    )
    SELECT
        (SELECT COUNT(DISTINCT {safe_col}) FROM {safe_table}) AS distinct_count,
        (SELECT array_agg(value ORDER BY value) FROM value_counts) AS distinct_values,
        (SELECT array_agg(frequency ORDER BY value) FROM value_counts) AS frequencies
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
