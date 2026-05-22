import uuid
from typing import Any, Required

from app_base.base.services.base import BaseContextKwargs, BaseCreateHooks, BaseUpdateHooks


class UserContextKwargs(BaseContextKwargs):
    """User tracking context kwargs."""

    user_id: Required[uuid.UUID]


class UserAwareHooksMixin[ModelType: Any, TUserContextKwargs: UserContextKwargs](
    BaseCreateHooks[ModelType, TUserContextKwargs], BaseUpdateHooks[ModelType, TUserContextKwargs]
):
    def _prepare_create_fields(self, obj_data, context: TUserContextKwargs, **update_fields: Any) -> dict[str, Any]:
        base = super()._prepare_create_fields(obj_data, context, **update_fields)
        if user_id := context.get("user_id"):
            return {**base, "created_by": user_id, "updated_by": user_id}
        return base

    def _prepare_update_fields(
        self, obj_data, context: TUserContextKwargs, partial: bool = True, **update_fields: Any
    ) -> dict[str, Any]:
        base = super()._prepare_update_fields(obj_data, context, partial=partial, **update_fields)
        if user_id := context.get("user_id"):
            return {**base, "updated_by": user_id}
        return base
