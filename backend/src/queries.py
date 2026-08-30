from sqlalchemy import text

def cardinality_query(table_name: str, column_name: str, cardinality_threshold: int) -> text:
    """
    Generates a SQL query to determine the cardinality of a column in a table.
    Returns the count of distinct values and an array of distinct values up to the specified threshold.
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
    """
    Generates a SQL query to retrieve sample values from a column in a table.
    Returns an array of sample values up to the specified sample size.
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