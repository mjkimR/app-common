import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeGuard

from qdrant_client import models

from app_prebuilt_search.errors import SearchConfigurationError, SearchInputError, SearchSourceError


@dataclass(frozen=True)
class KeywordFilter:
    kind: Literal["keyword"] = "keyword"


@dataclass(frozen=True)
class KeywordArrayFilter:
    kind: Literal["keywords"] = "keywords"


@dataclass(frozen=True)
class NumericFilter:
    kind: Literal["number"] = "number"


@dataclass(frozen=True)
class NumericRange:
    gt: float | None = None
    gte: float | None = None
    lt: float | None = None
    lte: float | None = None

    def values(self) -> dict[str, float]:
        return {k: v for k in ("gt", "gte", "lt", "lte") if (v := getattr(self, k)) is not None}


type FilterDefinition = KeywordFilter | KeywordArrayFilter | NumericFilter
type FilterValue = str | float | int | NumericRange


def _number(value: Any) -> TypeGuard[int | float]:
    return type(value) in (int, float) and math.isfinite(value)


class FilterPolicy:
    def __init__(self, definitions: Mapping[str, FilterDefinition]) -> None:
        self.definitions = dict(definitions)
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) for name in definitions):
            raise SearchConfigurationError("Filter names must be simple identifiers")
        if any(not isinstance(d, (KeywordFilter, KeywordArrayFilter, NumericFilter)) for d in definitions.values()):
            raise SearchConfigurationError("Unsupported filter definition")

    def validate_payload(self, values: Mapping[str, Any]) -> None:
        for key, value in values.items():
            definition = self.definitions.get(key)
            if isinstance(definition, KeywordFilter):
                valid = isinstance(value, str)
            elif isinstance(definition, KeywordArrayFilter):
                valid = isinstance(value, list) and all(isinstance(v, str) for v in value)
            else:
                valid = isinstance(definition, NumericFilter) and _number(value)
            if not valid:
                raise SearchSourceError(f"Invalid or undeclared filter payload: {key}")

    def validate_query(self, values: Mapping[str, FilterValue]) -> None:
        for key, value in values.items():
            definition = self.definitions.get(key)
            valid = False
            if isinstance(definition, (KeywordFilter, KeywordArrayFilter)):
                valid = isinstance(value, str)
            elif isinstance(definition, NumericFilter):
                valid = _number(value) or (
                    isinstance(value, NumericRange)
                    and bool(value.values())
                    and all(_number(v) for v in value.values().values())
                )
            if not valid:
                raise SearchInputError(f"Invalid or undeclared query filter: {key}")

    def query(self, scope: str, values: Mapping[str, FilterValue]) -> models.Filter:
        self.validate_query(values)
        conditions: list[models.Condition] = [
            models.FieldCondition(key="scope_id", match=models.MatchValue(value=scope))
        ]
        for key, value in values.items():
            field = f"filters.{key}"
            if isinstance(value, NumericRange):
                conditions.append(models.FieldCondition(key=field, range=models.Range(**value.values())))
            elif isinstance(self.definitions[key], NumericFilter):
                conditions.append(
                    models.FieldCondition(key=field, range=models.Range(gte=float(value), lte=float(value)))
                )
            else:
                conditions.append(models.FieldCondition(key=field, match=models.MatchValue(value=str(value))))
        return models.Filter(must=conditions)

    def matches(self, payload: Mapping[str, Any], values: Mapping[str, FilterValue]) -> bool:
        for key, value in values.items():
            actual = payload.get(key)
            definition = self.definitions[key]
            if isinstance(value, NumericRange):
                if not _number(actual):
                    return False
                for op, bound in value.values().items():
                    if not {"gt": actual > bound, "gte": actual >= bound, "lt": actual < bound, "lte": actual <= bound}[
                        op
                    ]:
                        return False
            elif isinstance(definition, KeywordArrayFilter):
                if not isinstance(actual, list) or value not in actual:
                    return False
            elif actual != value:
                return False
        return True

    def indexes(self) -> dict[str, models.PayloadSchemaType | models.KeywordIndexParams]:
        result: dict[str, models.PayloadSchemaType | models.KeywordIndexParams] = {
            "scope_id": models.KeywordIndexParams(type=models.KeywordIndexType.KEYWORD, is_tenant=True)
        }
        result.update(
            {
                f"filters.{name}": models.PayloadSchemaType.FLOAT
                if isinstance(d, NumericFilter)
                else models.PayloadSchemaType.KEYWORD
                for name, d in self.definitions.items()
            }
        )
        return result
