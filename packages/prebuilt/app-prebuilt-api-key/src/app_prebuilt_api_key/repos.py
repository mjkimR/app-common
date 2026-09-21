from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Machine, MachineKey


class ApiKeyRepository:
    async def machine(self, session: AsyncSession, machine_id: UUID) -> Machine | None:
        return await session.get(Machine, machine_id)

    async def machines(self, session: AsyncSession, offset: int, limit: int) -> list[Machine]:
        return list(await session.scalars(select(Machine).order_by(Machine.name).offset(offset).limit(limit)))

    async def machine_named(self, session: AsyncSession, name: str) -> Machine | None:
        return await session.scalar(select(Machine).where(Machine.name == name))

    async def add_machine(self, session: AsyncSession, machine: Machine) -> Machine:
        session.add(machine)
        await session.flush()
        return machine

    async def add_key(self, session: AsyncSession, key: MachineKey) -> MachineKey:
        session.add(key)
        await session.flush()
        return key

    async def key(self, session: AsyncSession, key_id: UUID) -> MachineKey | None:
        return await session.get(MachineKey, key_id)

    async def keys(self, session: AsyncSession, machine_id: UUID, offset: int, limit: int) -> list[MachineKey]:
        query = select(MachineKey).where(MachineKey.machine_id == machine_id)
        return list(
            await session.scalars(query.order_by(MachineKey.created_at, MachineKey.id).offset(offset).limit(limit))
        )
