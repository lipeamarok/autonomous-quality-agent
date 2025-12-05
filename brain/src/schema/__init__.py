"""
Schema module for UTDL.

Provides tools for schema generation, comparison, and validation.
"""

from .generator import (
    generate_pydantic_schema,
    load_canonical_schema,
    compare_schemas,
    export_pydantic_schema,
    validate_plan_against_schema,
    CANONICAL_SCHEMA_PATH,
    get_schema_validation_errors,
)

__all__ = [
    "generate_pydantic_schema",
    "load_canonical_schema",
    "compare_schemas",
    "export_pydantic_schema",
    "validate_plan_against_schema",
    "CANONICAL_SCHEMA_PATH",
]
