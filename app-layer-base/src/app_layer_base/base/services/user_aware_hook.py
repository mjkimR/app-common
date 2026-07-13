import uuid
from typing import Any, Required

from pydantic import BaseModel

from app_layer_base.base.services.hooks import (
    BaseContextKwargs,
    CreateHook,
    Operation,
    UpdateHook,
)


class UserContextKwargs(BaseContextKwargs):
    """User tracking context kwargs."""

    user_id: Required[uuid.UUID]


class UserAwareHook[ModelType: Any, TUserContextKwargs: UserContextKwargs](
    CreateHook[ModelType, TUserContextKwargs],
    UpdateHook[ModelType, TUserContextKwargs],
):
    """
    Stamps created_by / updated_by from ``context["user_id"]``.

    Stateless and dependency-free; a single instance can be shared.
    """

    def create_prepare_fields(
        self,
        op: Operation[TUserContextKwargs],
        data: BaseModel,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        if user_id := op.context.get("user_id"):
            return {**fields, "created_by": user_id, "updated_by": user_id}
        return fields

    def update_prepare_fields(
        self,
        op: Operation[TUserContextKwargs],
        data: BaseModel,
        fields: dict[str, Any],
        partial: bool = True,
    ) -> dict[str, Any]:
        if user_id := op.context.get("user_id"):
            return {**fields, "updated_by": user_id}
        return fields
