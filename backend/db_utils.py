"""
Database utility helpers for building safe parameterized dynamic queries.
"""
from typing import Any, Dict, Tuple, Optional


def build_dynamic_update_query(
    table_name: str,
    update_fields: Dict[str, Any],
    where_clause: str,
    where_params: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Constructs a parameterized SQL UPDATE query string and associated parameters dict.

    - Protects against column-name injection by enforcing valid Python identifiers.
    - If a field value is the literal string "NOW()", generates `column = NOW()`.
    - Otherwise generates `column = :u_<col>` and binds the value to prevent name collisions
      with where_params.
    """
    if not update_fields:
        raise ValueError("update_fields must not be empty")
    if not table_name.isidentifier():
        raise ValueError(f"Invalid table name: {table_name}")

    set_parts = []
    params = dict(where_params or {})

    for k, v in update_fields.items():
        if not k.isidentifier():
            raise ValueError(f"Invalid column name: {k}")

        if v == "NOW()":
            set_parts.append(f"{k} = NOW()")
        else:
            param_key = f"u_{k}"
            set_parts.append(f"{k} = :{param_key}")
            params[param_key] = v

    set_clause = ", ".join(set_parts)
    query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
    return query, params
