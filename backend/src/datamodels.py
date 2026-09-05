from enum import Enum
from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


class ColumnRelevanceType(str, Enum):
    INSIGHTFUL = "insightful"  # Metrics, dimensions, business attributes
    REFERENCE = "reference"    # Foreign keys, IDs, system metadata, surrogate keys

class SchemaEntryKind(str, Enum):
    TABLE = "table"
    COLUMN = "column"


class ColumnMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(
        ..., 
        description="Exact physical column name in the database."
    )
    data_type: str = Field(
        ..., 
        description="Database data type (e.g., VARCHAR(255), BIGINT, TIMESTAMP)."
    )
    description: str = Field(
        ..., 
        description="Semantic description explaining business meaning and contents."
    )
    relevance_type: ColumnRelevanceType = Field(
        default=ColumnRelevanceType.INSIGHTFUL,
        description="Classification of column utility for query planning."
    )
    is_primary_key: bool = Field(
        default=False, 
        description="Whether this column forms part of the primary key."
    )
    is_foreign_key: bool = Field(
        default=False, 
        description="Whether this column references another table."
    )
    foreign_key_reference: Optional[str] = Field(
        default=None, 
        description="Target table and column in 'table_name.column_name' format if is_foreign_key is True."
    )
    is_nullable: bool = Field(
        default=True, 
        description="Whether the column allows NULL values."
    )
    is_high_cardinality_string: bool = Field(
        default=False, 
        description="If True, values should be indexed in the Value Vector DB rather than stored in schema metadata."
    )
    sample_values: List[Union[str, int, float, bool]] = Field(
        default_factory=list, 
        description="Sample representative values to assist LLM with expected data formatting."
    )
    enum_values: List[str] = Field(
        default_factory=list, 
        description="Exhaustive list of possible values for low-cardinality categorical fields."
    )


class TableRelationship(BaseModel):
    model_config = ConfigDict(extra="ignore")

    foreign_key_column: str = Field(
        ..., 
        description="Local column name acting as foreign key."
    )
    target_table: str = Field(
        ..., 
        description="Target table name being referenced."
    )
    target_column: str = Field(
        ..., 
        description="Target column name being referenced."
    )
    relationship_type: Optional[str] = Field(
        default="many-to-one", 
        description="Relationship type e.g., 'one-to-many', 'many-to-one', 'one-to-one'."
    )


class TableMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    table_name: str = Field(
        ..., 
        description="Exact physical table name in the database."
    )
    schema_name: str = Field(
        default="public", 
        description="Database schema namespace (e.g., public, analytics, dbo)."
    )
    description: str = Field(
        ..., 
        description="High-level description of what this table represents and its business domain."
    )
    estimated_row_count: Optional[int] = Field(
        default=None, 
        description="Approximate row count to gauge table scale and query cost."
    )
    primary_keys: List[str] = Field(
        default_factory=list, 
        description="List of primary key column names."
    )
    relationships: List[TableRelationship] = Field(
        default_factory=list, 
        description="Explicit join paths originating from this table."
    )
    columns: List[ColumnMetadata] = Field(
        ..., 
        description="List of all column metadata definitions for this table."
    )

    def get_pruned_schema(self, include_reference_columns: bool = False) -> "TableMetadata":
        """
        Helper method to prune schema for context injection:
        Always keeps PKs, FKs, and insightful columns.
        Optionally retains reference columns.
        """
        pruned_cols = []
        for col in self.columns:
            if col.is_primary_key or col.is_foreign_key or include_reference_columns:
                pruned_cols.append(col)
            elif col.relevance_type == ColumnRelevanceType.INSIGHTFUL:
                pruned_cols.append(col)

        pruned_dict = self.model_dump()
        pruned_dict["columns"] = [col.model_dump() for col in pruned_cols]
        return TableMetadata.model_validate(pruned_dict)


class DatabaseSchemaIndex(BaseModel):
    model_config = ConfigDict(extra="ignore")

    database_name: str = Field(..., description="Target database identifier.")
    engine: str = Field(..., description="SQL dialect e.g., 'PostgreSQL', 'Snowflake', 'SQLite'.")
    tables: List[TableMetadata] = Field(..., description="Collection of all indexed database tables.")

class SchemaStoreMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    db : str = Field(..., description="Database name for which schema is stored.")
    kind: SchemaEntryKind = Field(..., description="Type of the schema entry.")
    table: str = Field(..., description="Table name for which values are stored.")
    column: Optional[str] = Field(None, description="Column name for COLUMN entries (None for TABLE entries).")
    value: Optional[str] = Field(None, description="The actual value stored in the schema store.")

class ValueStoreMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    db : str = Field(..., description="Database name for which schema is stored.")
    table: str = Field(..., description="Table name for which values are stored.")
    column: str = Field(..., description="Column name for which values are stored.")
    value: str = Field(..., description="The exact literal stored in the value store.")
    frequency: int = Field(..., description="The frequency of the value stored in the value store.")