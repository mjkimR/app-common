from typing import Any, Mapping

from app_base.adapter.nosql_db.interface import NoSQLDBProvider, import_error_handler
from app_base.adapter.nosql_db.registry import register_nosql_db
from app_base.config.nosql_db import FirestoreSettings, NoSQLDBSettings


@register_nosql_db("firestore")
class FirestoreProvider(NoSQLDBProvider):
    @classmethod
    def from_config(cls, settings: NoSQLDBSettings[FirestoreSettings]) -> "FirestoreProvider":
        with import_error_handler("firestore"):
            from google.cloud import firestore

        config: FirestoreSettings = settings.config

        if config.credentials_path:
            client = firestore.AsyncClient.from_service_account_json(
                config.credentials_path, project=config.project_id, database=config.database_id
            )
        else:
            client = firestore.AsyncClient(project=config.project_id, database=config.database_id)
        return cls(client)

    def close(self) -> None:
        # AsyncClient close is usually a no-op or handled by GC in google-cloud-firestore
        pass

    async def get_document(self, collection: str, document_id: str) -> Mapping[str, Any] | None:
        doc_ref = self.client.collection(collection).document(document_id)
        doc = await doc_ref.get()
        return doc.to_dict() if doc.exists else None

    async def create_document(self, collection: str, document_id: str, data: Mapping[str, Any]) -> None:
        doc_ref = self.client.collection(collection).document(document_id)
        await doc_ref.set(data)

    async def update_document(self, collection: str, document_id: str, data: Mapping[str, Any]) -> None:
        doc_ref = self.client.collection(collection).document(document_id)
        await doc_ref.update(data)

    async def delete_document(self, collection: str, document_id: str) -> None:
        doc_ref = self.client.collection(collection).document(document_id)
        await doc_ref.delete()

    async def list_documents(
        self, collection: str, filters: list[tuple[str, str, Any]] | None = None
    ) -> list[Mapping[str, Any]]:
        query = self.client.collection(collection)
        if filters:
            for field, op, value in filters:
                query = query.where(field, op, value)

        docs = await query.get()
        return [doc.to_dict() for doc in docs]
