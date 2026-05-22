from typing import Any

from pydantic import BaseModel

from app_base.adapter.nosql_db.interface import NoSQLDBProvider
from app_base.adapter.nosql_db.query_options import NoSQLListQueryOptions
from app_base.base.schemas.paginated import PaginatedList


class NoSQLRepository[
    ModelType: Any,
    CreateSchemaType: BaseModel,
    PutSchemaType: BaseModel,
    PatchSchemaType: BaseModel,
]:
    """
    Base repository class for NoSQL databases.
    """

    collection_name: str
    model: type[ModelType]

    def model_name(self) -> str:
        return self.model.__name__

    def model_repr(self, document_id: str) -> str:
        return f"{self.model_name()}(id={document_id})"

    async def get_by_id(self, provider: NoSQLDBProvider, document_id: str) -> ModelType | None:
        data = await provider.get_document(self.collection_name, document_id)
        if not data:
            return None
        return self.model(**data)

    async def create(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_in: CreateSchemaType,
        **extra_fields: Any,
    ) -> ModelType:
        obj_dict = obj_in.model_dump()
        obj_dict.update(extra_fields)
        await provider.create_document(self.collection_name, document_id, obj_dict)
        return self.model(**obj_dict)

    async def put(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_in: PutSchemaType,
        **extra_fields: Any,
    ) -> ModelType | None:
        """Full update (PUT) - all fields replaced."""
        update_data = obj_in.model_dump()
        update_data.update(extra_fields)
        await provider.update_document(self.collection_name, document_id, update_data)
        return await self.get_by_id(provider, document_id)

    async def patch(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_in: PatchSchemaType,
        **extra_fields: Any,
    ) -> ModelType | None:
        """Partial update (PATCH) - only set fields updated."""
        update_data = obj_in.model_dump(exclude_unset=True)
        update_data.update(extra_fields)
        await provider.update_document(self.collection_name, document_id, update_data)
        return await self.get_by_id(provider, document_id)

    async def update(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_in: PutSchemaType,
        **extra_fields: Any,
    ) -> ModelType | None:
        """Deprecated: use put() or patch() instead."""
        return await self.patch(provider, document_id, obj_in, **extra_fields)

    async def delete(self, provider: NoSQLDBProvider, document_id: str) -> bool:
        await provider.delete_document(self.collection_name, document_id)
        return True

    async def get_multi(
        self,
        provider: NoSQLDBProvider,
        query_options: NoSQLListQueryOptions | None = None,
    ) -> PaginatedList[ModelType]:
        query_options = query_options or NoSQLListQueryOptions()
        docs = await provider.list_documents(self.collection_name, filters=list(query_options.filters))

        total_count = len(docs)
        paged_docs = docs[query_options.offset : query_options.offset + query_options.limit]

        items = [self.model(**doc) for doc in paged_docs]
        return PaginatedList(
            items=items,
            total_count=total_count,
            offset=query_options.offset,
            limit=query_options.limit,
        )

    async def exists(self, provider: NoSQLDBProvider, document_id: str) -> bool:
        doc = await provider.get_document(self.collection_name, document_id)
        return doc is not None
