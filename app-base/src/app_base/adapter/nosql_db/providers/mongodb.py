from collections.abc import Mapping
from typing import Any

from app_base.adapter.nosql_db.interface import NoSQLDBProvider, import_error_handler
from app_base.adapter.nosql_db.registry import register_nosql_db
from app_base.config.nosql_db import MongoDBSettings, NoSQLDBSettings


@register_nosql_db("mongodb")
class MongoDBProvider(NoSQLDBProvider):
    @classmethod
    def from_config(cls, settings: NoSQLDBSettings[MongoDBSettings]) -> "MongoDBProvider":
        with import_error_handler("mongodb"):
            from motor.motor_asyncio import AsyncIOMotorClient

        config: MongoDBSettings = settings.config
        client = AsyncIOMotorClient(config.url)
        return cls(client)

    def close(self) -> None:
        if self.client:
            self.client.close()

    async def get_document(self, collection: str, document_id: str) -> Mapping[str, Any] | None:
        # Note: document_id might need to be converted to ObjectId depending on usage
        # This is a generic draft.
        db = self.client.get_default_database()
        doc = await db[collection].find_one({"_id": document_id})
        return doc

    async def create_document(self, collection: str, document_id: str, data: Mapping[str, Any]) -> None:
        db = self.client.get_default_database()
        doc = dict(data)
        doc["_id"] = document_id
        await db[collection].insert_one(doc)

    async def update_document(self, collection: str, document_id: str, data: Mapping[str, Any]) -> None:
        db = self.client.get_default_database()
        await db[collection].update_one({"_id": document_id}, {"$set": data})

    async def delete_document(self, collection: str, document_id: str) -> None:
        db = self.client.get_default_database()
        await db[collection].delete_one({"_id": document_id})

    async def list_documents(
        self, collection: str, filters: list[tuple[str, str, Any]] | None = None
    ) -> list[Mapping[str, Any]]:
        db = self.client.get_default_database()
        query_filter = {}
        if filters:
            # Simple conversion of (field, op, value) to MongoDB filter
            # op: '==', '>', '<', '>=', '<=', 'array_contains', etc.
            # This is a very basic mapping.
            op_map = {
                "==": "$eq",
                ">": "$gt",
                "<": "$lt",
                ">=": "$gte",
                "<=": "$lte",
                "in": "$in",
                "array_contains": "$elemMatch",  # Not exactly same but similar concept
            }
            for field, op, value in filters:
                mongo_op = op_map.get(op, "$eq")
                query_filter[field] = {mongo_op: value}

        cursor = db[collection].find(query_filter)
        return await cursor.to_list(length=None)
