from typing import Annotated
from uuid import UUID

from app_layer_base.base.exceptions.basic import ConflictException
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..database import get_api_key_session_maker
from ..schemas import KeyCreate, KeyIssued, KeyRead, MachineCreate, MachinePrincipal, MachineRead, MachineUpdate
from ..services import ApiKeyService


def get_machine_scopes() -> frozenset[str]:
    """Hosts override this allowlist; applications interpret the scopes they register."""
    return frozenset()


class ApiKeyUseCase:
    def __init__(
        self,
        maker: Annotated[async_sessionmaker[AsyncSession], Depends(get_api_key_session_maker)],
        scopes: Annotated[frozenset[str], Depends(get_machine_scopes)],
    ):
        self.maker = maker
        self.service = ApiKeyService(scopes)

    async def create(self, data: MachineCreate) -> MachineRead:
        try:
            async with AsyncTransaction(self.maker) as session:
                return MachineRead.model_validate(await self.service.create(session, data))
        except IntegrityError:
            raise ConflictException("Machine name already exists") from None

    async def machines(self, offset: int, limit: int) -> list[MachineRead]:
        async with self.maker() as session:
            return [MachineRead.model_validate(m) for m in await self.service.repo.machines(session, offset, limit)]

    async def update(self, machine_id: UUID, data: MachineUpdate) -> MachineRead:
        async with AsyncTransaction(self.maker) as session:
            return MachineRead.model_validate(await self.service.update(session, machine_id, data))

    async def issue(self, machine_id: UUID, data: KeyCreate) -> KeyIssued:
        async with AsyncTransaction(self.maker) as session:
            return await self.service.issue(session, machine_id, data)

    async def keys(self, machine_id: UUID, offset: int, limit: int) -> list[KeyRead]:
        async with self.maker() as session:
            await self.service.machine(session, machine_id)
            return [KeyRead.model_validate(k) for k in await self.service.repo.keys(session, machine_id, offset, limit)]

    async def revoke(self, machine_id: UUID, key_id: UUID) -> KeyRead:
        async with AsyncTransaction(self.maker) as session:
            return KeyRead.model_validate(await self.service.revoke(session, machine_id, key_id))

    async def authenticate(self, raw: str) -> MachinePrincipal:
        # Close authentication's read transaction before the application's operation begins.
        async with self.maker() as session:
            return await self.service.authenticate(session, raw)
