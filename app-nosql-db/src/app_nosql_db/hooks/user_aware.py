from typing import Any, Required

from app_nosql_db.hooks.base import (
    BaseNoSQLContextKwargs,
    BaseNoSQLCreateHooks,
    BaseNoSQLUpdateHooks,
)


class NoSQLUserContextKwargs(BaseNoSQLContextKwargs):
    """User tracking context kwargs for NoSQL."""

    user_id: Required[str]


class NoSQLUserAwareHooksMixin[ModelType: Any, TNoSQLUserContextKwargs: NoSQLUserContextKwargs](
    BaseNoSQLCreateHooks[ModelType, TNoSQLUserContextKwargs],
    BaseNoSQLUpdateHooks[ModelType, TNoSQLUserContextKwargs],
):
    def _prepare_create_fields(
        self, obj_data, context: TNoSQLUserContextKwargs, **update_fields: Any
    ) -> dict[str, Any]:
        base = super()._prepare_create_fields(obj_data, context, **update_fields)
        if user_id := context.get("user_id"):
            return {**base, "created_by": user_id, "updated_by": user_id}
        return base

    def _prepare_update_fields(
        self, obj_data, context: TNoSQLUserContextKwargs, partial: bool = True, **update_fields: Any
    ) -> dict[str, Any]:
        base = super()._prepare_update_fields(obj_data, context, **update_fields)
        if user_id := context.get("user_id"):
            return {**base, "updated_by": user_id}
        return base
