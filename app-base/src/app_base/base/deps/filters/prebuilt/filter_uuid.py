from uuid import UUID

from app_base.base.deps.filters.base import SimpleFilterCriteriaBase
from sqlalchemy.orm import DeclarativeBase


class UUIDFilter(SimpleFilterCriteriaBase):
    def __init__(self, model: type[DeclarativeBase], field_name: str, alias=None, description=None):
        self.model = model
        self.field_name = field_name

        if not hasattr(model, field_name):
            raise ValueError(f"Model '{model.__name__}' does not have a field named '{field_name}'")

        alias = alias or f"filter_{field_name}"
        description = description or f"Filter {model.__name__} by field '{field_name}' equal to the provided UUID"
        super().__init__(
            alias=alias,
            bound_type=UUID,
            description=description,
        )

    def _filter_logic(self, value):
        if value is None:
            return None
        model_field = getattr(self.model, self.field_name)
        return model_field == value


class UUIDAnyFilter(SimpleFilterCriteriaBase):
    def __init__(self, model: type[DeclarativeBase], field_name: str, alias=None, description=None):
        self.model = model
        self.field_name = field_name

        if not hasattr(model, field_name):
            raise ValueError(f"Model '{model.__name__}' does not have a field named '{field_name}'")

        alias = alias or f"filter_{field_name}_any"
        description = (
            description or f"Filter {model.__name__} by field '{field_name}' matching any of the provided UUIDs"
        )
        super().__init__(
            alias=alias,
            bound_type=list[UUID],
            description=description,
        )

    def _filter_logic(self, value):
        if value is None or not isinstance(value, list) or len(value) == 0:
            return None
        model_field = getattr(self.model, self.field_name)
        return model_field.in_(value)
