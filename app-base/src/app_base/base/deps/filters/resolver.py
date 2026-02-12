import inspect
from typing import Any, Sequence

from sqlalchemy import ColumnElement

from app_base.base.deps.filters.base import SqlFilterCriteriaBase
from app_base.base.deps.filters.combine import combine_filter_conditions
from app_base.base.deps.filters.exceptions import InvalidValueError


def _process_filters(target_filters: Sequence[tuple[SqlFilterCriteriaBase, Any]]) -> list[ColumnElement]:
    filters = []
    for filter_criteria, value in target_filters:
        _filter = filter_criteria.build_filter()

        signature = inspect.signature(_filter)
        params = list(signature.parameters.values())
        positional_param_count = len(
            [
                param
                for param in params
                if param.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                )
            ]
        )
        has_varargs = any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params)
        has_varkw = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params)

        if positional_param_count <= 1 and not has_varargs and not has_varkw:
            _filter_condition = _filter(value)
        else:
            if isinstance(value, dict):
                _filter_condition = _filter(**value)
            elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                _filter_condition = _filter(*value)
            else:
                raise InvalidValueError(
                    "Filter dependency expects multiple arguments; "
                    "value must be a dict for keyword args or a non-string sequence for positional args."
                )
        filters.append(_filter_condition)
    return combine_filter_conditions(*filters)


def resolve_filter(criteria: SqlFilterCriteriaBase, value: Any) -> list[ColumnElement]:
    """
    Resolves a single filter criteria and its corresponding value into SQLAlchemy filter expressions.

    Args:
        criteria (SqlFilterCriteriaBase): The filter criteria instance.
        value (Any): The value for the filter.

    Returns:
        List of SQLAlchemy filter expressions.
    """
    return _process_filters([(criteria, value)])


def resolve_filters(*args: tuple[SqlFilterCriteriaBase, Any]) -> list[ColumnElement]:
    """
    Resolves a list of filter criteria and their corresponding values into SQLAlchemy filter expressions.

    Args:
        *args (tuple[SqlFilterCriteriaBase, Any]): Tuples of filter criteria instances and their values.

    Returns:
        List of SQLAlchemy filter expressions.
    """
    return _process_filters(args)
