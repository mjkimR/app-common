from app_base.base.deps.filters.base import SimpleFilterCriteriaBase
from sqlalchemy.orm import DeclarativeBase


class StringILikeFilter(SimpleFilterCriteriaBase):
    def __init__(self, model: type[DeclarativeBase], field_name: str, alias=None, description=None):
        self.model = model
        self.field_name = field_name

        if not hasattr(model, field_name):
            raise ValueError(f"Model '{model.__name__}' does not have a field named '{field_name}'")

        alias = alias or f"filter_{field_name}"
        description = (
            description or f"Filter {model.__name__} by field '{field_name}' using case-insensitive substring match"
        )
        super().__init__(
            alias=alias,
            bound_type=str,
            description=description,
        )

    def _filter_logic(self, value):
        if value is None:
            return None
        model_field = getattr(self.model, self.field_name)
        return model_field.ilike(f"%{value}%")


class StringLikeFilter(SimpleFilterCriteriaBase):
    def __init__(self, model: type[DeclarativeBase], field_name: str, alias=None, description=None):
        self.model = model
        self.field_name = field_name

        if not hasattr(model, field_name):
            raise ValueError(f"Model '{model.__name__}' does not have a field named '{field_name}'")

        alias = alias or f"filter_{field_name}"
        description = description or f"Filter {model.__name__} by field '{field_name}' using substring match"
        super().__init__(
            alias=alias,
            bound_type=str,
            description=description,
        )

    def _filter_logic(self, value):
        if value is None:
            return None
        model_field = getattr(self.model, self.field_name)
        return model_field.like(f"%{value}%")


class StringExactFilter(SimpleFilterCriteriaBase):
    def __init__(self, model: type[DeclarativeBase], field_name: str, alias=None, description=None):
        self.model = model
        self.field_name = field_name

        if not hasattr(model, field_name):
            raise ValueError(f"Model '{model.__name__}' does not have a field named '{field_name}'")

        alias = alias or f"filter_{field_name}"
        description = description or f"Filter {model.__name__} by field '{field_name}' using exact match"
        super().__init__(
            alias=alias,
            bound_type=str,
            description=description,
        )

    def _filter_logic(self, value):
        if value is None:
            return None
        model_field = getattr(self.model, self.field_name)
        return model_field == value


class StringAnyFilter(SimpleFilterCriteriaBase):
    def __init__(self, model: type[DeclarativeBase], field_name: str, alias=None, description=None):
        self.model = model
        self.field_name = field_name

        if not hasattr(model, field_name):
            raise ValueError(f"Model '{model.__name__}' does not have a field named '{field_name}'")

        alias = alias or f"filter_{field_name}_any"
        description = (
            description or f"Filter {model.__name__} by field '{field_name}' matching any of the provided values"
        )
        super().__init__(
            alias=alias,
            bound_type=list[str],
            description=description,
        )

    def _filter_logic(self, value):
        if value is None or not isinstance(value, list) or len(value) == 0:
            return None
        model_field = getattr(self.model, self.field_name)
        return model_field.in_(value)


class EnumFilter(SimpleFilterCriteriaBase):
    def __init__(self, model: type[DeclarativeBase], field_name: str, enum_type: type, alias=None, description=None):
        self.model = model
        self.field_name = field_name
        self.enum_type = enum_type

        if not hasattr(model, field_name):
            raise ValueError(f"Model '{model.__name__}' does not have a field named '{field_name}'")

        alias = alias or f"filter_{field_name}"
        description = (
            description or f"Filter {model.__name__} by field '{field_name}' matching {enum_type.__name__} values"
        )
        super().__init__(
            alias=alias,
            bound_type=enum_type,
            description=description,
        )

    def _filter_logic(self, value):
        if value is None:
            return None
        model_field = getattr(self.model, self.field_name)
        return model_field == value.value
