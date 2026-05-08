from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

from app_base.adapter.nosql_db.interface import NoSQLDBProvider
from app_base.base.schemas.paginated import PaginatedList

ModelType = TypeVar("ModelType", bound=Any)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class NoSQLRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base repository class for NoSQL databases.
    """

    collection_name: str
    model: type[ModelType]

    def model_name(self) -> str:
        return self.model.__name__

    def model_repr(self, document_id: str) -> str:
        return f"{self.model_name()}(id={document_id})"

    async def get_by_id(self, provider: NoSQLDBProvider, document_id: str) -> Optional[ModelType]:
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

    async def update(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_in: UpdateSchemaType,
        **extra_fields: Any,
    ) -> Optional[ModelType]:
        update_data = obj_in.model_dump(exclude_unset=True)
        update_data.update(extra_fields)
        await provider.update_document(self.collection_name, document_id, update_data)

        existing = await self.get_by_id(provider, document_id)
        return existing

    async def delete(self, provider: NoSQLDBProvider, document_id: str) -> bool:
        await provider.delete_document(self.collection_name, document_id)
        return True

    async def get_multi(
        self,
        provider: NoSQLDBProvider,
        filters: list[tuple[str, str, Any]] | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> PaginatedList[ModelType]:
        docs = await provider.list_documents(self.collection_name, filters=filters)

        total_count = len(docs)
        paged_docs = docs[offset : offset + limit]

        items = [self.model(**doc) for doc in paged_docs]
        return PaginatedList(
            items=items,
            total_count=total_count,
            offset=offset,
            limit=limit,
        )

    async def exists(self, provider: NoSQLDBProvider, document_id: str) -> bool:
        doc = await provider.get_document(self.collection_name, document_id)
        return doc is not None
