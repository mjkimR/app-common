from abc import ABCMeta, abstractmethod
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.services.hooks import BaseContextKwargs, DeleteHook, Operation


class DetailDeleteResponseHook[ModelType: Any, TContextKwargs: BaseContextKwargs](
    DeleteHook[TContextKwargs], metaclass=ABCMeta
):
    """
    Puts a human-readable representation of the deleted row on the response.

    The row is read before the delete and the text is stashed on the operation,
    keyed by pk -- not on the hook -- so that delete_multi gives each item its
    own representation and nothing leaks between calls.
    """

    _STATE_KEY = "detail_delete_represent_text"

    @abstractmethod
    def represent(self, obj: ModelType) -> str:
        """[Override Required] Render the object being deleted as a string."""

    def _texts(self, op: Operation[TContextKwargs]) -> dict[str, str]:
        return op.state.setdefault(self._STATE_KEY, {})

    @asynccontextmanager
    async def delete_context(self, op: Operation[TContextKwargs], pk: PrimaryKeyType) -> AsyncIterator[None]:
        obj = await op.repo.get_by_pk(op.session, pk=pk)
        if obj is not None:
            self._texts(op)[str(pk)] = self.represent(obj)
        yield

    async def delete_post(
        self, op: Operation[TContextKwargs], pk: PrimaryKeyType, result: DeleteResponse
    ) -> DeleteResponse:
        text = self._texts(op).get(str(pk))
        if text is not None:
            result.representation = text
        return result

    # ------------------------------------------------------------------
    # delete_multi: this hook has nothing to say.
    #
    # MultipleDeleteResponse has no per-item representation field, so reading
    # every row just to render text the caller can never see would be N queries
    # for nothing. Override these two if you want bulk representations somewhere
    # (MultipleDeleteResponse.meta is the natural home).
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def delete_context_multi(
        self, op: Operation[TContextKwargs], pks: Sequence[PrimaryKeyType]
    ) -> AsyncIterator[None]:
        yield

    async def delete_post_multi(
        self,
        op: Operation[TContextKwargs],
        pks: Sequence[PrimaryKeyType],
        result: MultipleDeleteResponse,
    ) -> MultipleDeleteResponse:
        return result
