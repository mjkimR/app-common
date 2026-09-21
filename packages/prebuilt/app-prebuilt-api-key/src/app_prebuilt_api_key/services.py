import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app_layer_base.base.exceptions.basic import BadRequestException, ConflictException, NotFoundException
from app_layer_base.utils.time_util import get_current_utc_time
from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import InvalidApiKey
from .models import Machine, MachineKey
from .repos import ApiKeyRepository
from .schemas import KeyCreate, KeyIssued, MachineCreate, MachinePrincipal, MachineUpdate


def utc(value: datetime) -> datetime:
    # SQLite returns timezone-free values for DateTime(timezone=True).
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class ApiKeyService:
    def __init__(self, allowed_scopes: frozenset[str], repo: ApiKeyRepository | None = None):
        self.allowed_scopes = allowed_scopes
        self.repo = repo or ApiKeyRepository()

    def scopes(self, values: list[str]) -> list[str]:
        if not set(values) <= self.allowed_scopes:
            raise BadRequestException("Unsupported machine scopes")
        return sorted(set(values))

    async def machine(self, session: AsyncSession, machine_id: UUID) -> Machine:
        machine = await self.repo.machine(session, machine_id)
        if machine is None:
            raise NotFoundException("Machine not found")
        return machine

    async def create(self, session: AsyncSession, data: MachineCreate) -> Machine:
        if await self.repo.machine_named(session, data.name):
            raise ConflictException("Machine name already exists")
        return await self.repo.add_machine(session, Machine(name=data.name, scopes=self.scopes(data.scopes)))

    async def update(self, session: AsyncSession, machine_id: UUID, data: MachineUpdate) -> Machine:
        machine = await self.machine(session, machine_id)
        if data.scopes is not None:
            machine.scopes = self.scopes(data.scopes)
        if data.is_active is not None:
            machine.is_active = data.is_active
        await session.flush()
        return machine

    async def issue(self, session: AsyncSession, machine_id: UUID, data: KeyCreate) -> KeyIssued:
        machine = await self.machine(session, machine_id)
        if not machine.is_active:
            raise BadRequestException("Activate the machine before issuing a key")
        if data.expires_at is not None and data.expires_at <= get_current_utc_time():
            raise BadRequestException("Expiry must be in the future")
        key_id = uuid4()
        raw = f"ak_{key_id.hex}_{secrets.token_urlsafe(32)}"
        key = await self.repo.add_key(
            session,
            MachineKey(
                id=key_id,
                machine_id=machine_id,
                label=data.label,
                secret_hash=digest(raw),
                expires_at=utc(data.expires_at) if data.expires_at is not None else None,
            ),
        )
        return KeyIssued.model_validate(
            {**{name: getattr(key, name) for name in KeyIssued.model_fields if name != "key"}, "key": raw}
        )

    async def revoke(self, session: AsyncSession, machine_id: UUID, key_id: UUID) -> MachineKey:
        key = await self.repo.key(session, key_id)
        if key is None or key.machine_id != machine_id:
            raise NotFoundException("API key not found")
        if key.revoked_at is None:
            key.revoked_at = get_current_utc_time()
            await session.flush()
        return key

    async def authenticate(self, session: AsyncSession, raw: str) -> MachinePrincipal:
        try:
            prefix, identifier, secret = raw.split("_", 2)
            if prefix != "ak" or len(secret) < 32 or len(raw) > 256:
                raise ValueError
            key_id = UUID(hex=identifier)
        except ValueError:
            raise InvalidApiKey() from None
        key = await self.repo.key(session, key_id)
        if key is None or not secrets.compare_digest(key.secret_hash, digest(raw)):
            raise InvalidApiKey()
        if key.revoked_at is not None or (key.expires_at is not None and utc(key.expires_at) <= get_current_utc_time()):
            raise InvalidApiKey()
        machine = await self.repo.machine(session, key.machine_id)
        if machine is None or not machine.is_active:
            raise InvalidApiKey()
        return MachinePrincipal(
            machine_id=machine.id, key_id=key.id, name=machine.name, scopes=frozenset(machine.scopes)
        )
