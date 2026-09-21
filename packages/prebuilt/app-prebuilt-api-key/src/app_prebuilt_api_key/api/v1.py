from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from ..deps import require_key_admin
from ..schemas import KeyCreate, KeyIssued, KeyRead, MachineCreate, MachineRead, MachineUpdate
from ..usecases import ApiKeyUseCase

router = APIRouter(prefix="/machines", tags=["Machine API keys"], dependencies=[Depends(require_key_admin)])
UseCase = Annotated[ApiKeyUseCase, Depends()]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=200)]


@router.post("", response_model=MachineRead, status_code=201)
async def create_machine(data: MachineCreate, usecase: UseCase) -> MachineRead:
    return await usecase.create(data)


@router.get("", response_model=list[MachineRead])
async def list_machines(usecase: UseCase, offset: Offset = 0, limit: Limit = 100) -> list[MachineRead]:
    return await usecase.machines(offset, limit)


@router.patch("/{machine_id}", response_model=MachineRead)
async def update_machine(machine_id: UUID, data: MachineUpdate, usecase: UseCase) -> MachineRead:
    return await usecase.update(machine_id, data)


@router.post("/{machine_id}/keys", response_model=KeyIssued, status_code=201)
async def issue_key(machine_id: UUID, data: KeyCreate, response: Response, usecase: UseCase) -> KeyIssued:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return await usecase.issue(machine_id, data)


@router.get("/{machine_id}/keys", response_model=list[KeyRead])
async def list_keys(machine_id: UUID, usecase: UseCase, offset: Offset = 0, limit: Limit = 100) -> list[KeyRead]:
    return await usecase.keys(machine_id, offset, limit)


@router.delete("/{machine_id}/keys/{key_id}", response_model=KeyRead)
async def revoke_key(machine_id: UUID, key_id: UUID, usecase: UseCase) -> KeyRead:
    return await usecase.revoke(machine_id, key_id)
