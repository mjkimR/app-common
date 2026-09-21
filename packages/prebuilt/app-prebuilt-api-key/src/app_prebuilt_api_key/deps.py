import secrets
from typing import Annotated

from fastapi import Depends
from fastapi.security import APIKeyHeader

from .config import ApiKeySettings, get_api_key_settings
from .exceptions import InvalidApiKey
from .schemas import MachinePrincipal
from .usecases import ApiKeyUseCase

machine_key_header = APIKeyHeader(name="X-API-Key", scheme_name="MachineApiKey", auto_error=False)
root_key_header = APIKeyHeader(name="X-Root-API-Key", scheme_name="RootApiKey", auto_error=False)


def require_key_admin(
    settings: Annotated[ApiKeySettings, Depends(get_api_key_settings)],
    key: Annotated[str | None, Depends(root_key_header)],
) -> None:
    """Root authenticates only management routes. Hosts may add human administrators."""
    expected = settings.root_key.get_secret_value() if settings.root_key else None
    if not expected or not key or not secrets.compare_digest(key.encode(), expected.encode()):
        raise InvalidApiKey()


async def get_machine_principal(
    key: Annotated[str | None, Depends(machine_key_header)],
    usecase: Annotated[ApiKeyUseCase, Depends()],
) -> MachinePrincipal:
    if not key:
        raise InvalidApiKey()
    return await usecase.authenticate(key)
