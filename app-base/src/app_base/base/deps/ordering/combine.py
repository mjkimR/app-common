from typing import Callable, List, Optional

from fastapi import Query
from sqlalchemy.sql import ColumnElement

from app_base.base.deps.ordering.base import OrderByCriteria


def create_order_by_dependency(
    *criteria: OrderByCriteria,
    default_order: str = "-created_at",
    tie_breaker: Optional[OrderByCriteria] = None,
) -> Callable:
    """Creates a FastAPI dependency for handling dynamic order_by query parameters.

    This function aggregates multiple OrderByCriteria into a single dependency that parses
    comma-separated sorting fields, applies the corresponding SQLAlchemy logic, and
    optionally appends a tie-breaker.

    Args:
        *criteria (OrderByCriteria): A sequence of order by criteria instances.
        default_order (str, optional): The default order_by string to use if none is provided.
            Defaults to "-created_at".
        tie_breaker (Optional[OrderByCriteria], optional): An optional criteria to append as a tie-breaker
            if not already present in the query. Defaults to None.

    Returns:
        Callable: A FastAPI dependency yielding a list of SQLAlchemy ColumnElement expressions.
    """
    registry = {c.alias: c for c in criteria}

    # Generate description for OpenAPI
    desc_lines = ["**Order by options:**\n"]
    for alias, criterion in registry.items():
        if criterion.description:
            raw_desc = criterion.description.strip()
            lines = raw_desc.splitlines()
            desc_lines.append(f"* `{alias}`: {lines[0]}")
            for line in lines[1:]:
                stripped_line = line.strip()
                if stripped_line:
                    desc_lines.append(f"  {stripped_line}")
        else:
            desc_lines.append(f"* `{alias}`")

    desc_lines.append("\n**Usage:**")
    desc_lines.append("* Prefix with `-` for descending order (e.g., `-title`).")
    desc_lines.append("* Multiple fields can be separated by commas (e.g., `-created_at,title`).")
    desc_lines.append(f"* **Default:** `{default_order}`")

    final_description = "\n".join(desc_lines)

    def dependency(order_by: Optional[str] = Query(default=None, description=final_description)) -> List[ColumnElement]:
        if not order_by:
            order_by = default_order

        tokens = [t.strip() for t in order_by.split(",") if t.strip()]
        result_clauses = []
        used_aliases = set()

        for token in tokens:
            is_desc = False
            field_name = token

            if token.startswith("-"):
                is_desc = True
                field_name = token[1:]

            if field_name in registry:
                handler = registry[field_name]
                result_clauses.append(handler(desc=is_desc))
                used_aliases.add(field_name)

        # Append tie-breaker if configured, results exist, and it wasn't manually selected
        if tie_breaker and result_clauses and (tie_breaker.alias not in used_aliases):
            result_clauses.append(tie_breaker(desc=False))

        return result_clauses

    return dependency
