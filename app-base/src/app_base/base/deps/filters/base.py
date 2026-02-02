import abc
from abc import ABCMeta
from typing import Any, Callable, Optional, Union

from fastapi import Query
from sqlalchemy import ColumnElement

from app_base.base.deps.filters.exceptions import (
    ConfigurationError,
)


class SqlFilterCriteriaBase(metaclass=ABCMeta):
    """
    Abstract base class for creating declarative SQL filter criteria.

    This class is the foundation for all filter criteria. Subclasses define how a particular field or relationship should be filtered.
    """

    @abc.abstractmethod
    def build_filter(
        self,
    ) -> Callable[..., Optional[Union[ColumnElement, list[ColumnElement]]]]:
        """Creates a FastAPI dependency that generates a filter condition.

        This abstract method must be implemented by all subclasses. The
        implementation should not return a filter condition directly. Instead,
        it must return a callable (a function) that FastAPI can use as a
        dependency. FastAPI will resolve this dependency for each incoming
        request, calling it with the appropriate query parameters to generate
        the live SQLAlchemy filter expression.

        Returns:
            A FastAPI dependency. When called, it returns a SQLAlchemy
            filter condition (`ColumnElement`), a list of conditions, or
            `None` if the filter is not active for the current request.
        """
        raise NotImplementedError


class SimpleFilterCriteriaBase(SqlFilterCriteriaBase):
    """
    Base class for simple, single-parameter filter criteria.

    This class is intended for filter criteria that map a single query parameter to a single SQLAlchemy filter expression. Subclasses must implement `_filter_logic` to define the actual filtering behavior.
    """

    def __init__(
        self,
        alias: str,
        bound_type: type,
        description: Optional[str] = None,
        **query_params: Any,
    ):
        """
        Initialize a simple filter criterion.

        Args:
            alias (str): The query parameter name (defaults to attribute name if None).
            bound_type (type): The type to bind the query parameter to.
            description (Optional[str]): Description for OpenAPI docs.
            **query_params: Additional keyword arguments for FastAPI's Query.
        """
        self.alias = alias
        self.bound_type = bound_type
        self.description = description
        self.query_params = query_params

    @abc.abstractmethod
    def _filter_logic(self, value):
        """
        Implement the actual SQLAlchemy filter logic for this criterion.

        Args:
            value: The value from the query parameter.

        Returns:
            A SQLAlchemy filter expression, or None if not active.
        """
        raise NotImplementedError

    def build_filter(self) -> Callable[..., ColumnElement | list[ColumnElement] | None]:
        """
        Build a FastAPI dependency that generates a filter condition for this criterion.

        Returns:
            Callable: A FastAPI dependency function that returns a filter expression or None.
        """
        if not self.alias:
            raise ConfigurationError(
                "Filter criteria is missing an 'alias'. Please provide an alias (query parameter name)."
            )
        if self.bound_type is None:
            raise ConfigurationError(
                "Filter criteria is missing a 'bound_type'. "
                "Please specify the type to bind the query parameter to (e.g., str, int)."
            )
        description = self.description or f"Filter query parameter ({self.alias})"

        def filter_dependency(
            value: Optional[self.bound_type] = Query(  # type: ignore  # noqa: B008
                default=None,
                alias=self.alias,
                description=description,
                **self.query_params,
            ),
        ) -> Optional[ColumnElement]:
            """
            FastAPI dependency that returns the filter expression for this criterion.

            Args:
                value: The value from the query parameter (injected by FastAPI).

            Returns:
                Optional[ColumnElement]: The SQLAlchemy filter expression, or None if not active.
            """
            return self._filter_logic(value=value)

        return filter_dependency
