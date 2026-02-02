#!/usr/bin/env python
import argparse
import re
from pathlib import Path


def pluralize(name: str) -> str:
    """A simple pluralizer."""
    if name.endswith("y"):
        return name[:-1] + "ies"
    if name.endswith("s"):
        return name + "es"
    return name + "s"


def to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def update_router(plural_name: str):
    """
    Updates backend/app/router.py to include the new module's router.
    """
    router_path = Path("backend/app/router.py")
    try:
        lines = router_path.read_text().splitlines()
        if not lines:
            print(f"Warning: {router_path} is empty. Skipping update.")
            return

        # Add import
        last_feature_import_index = -1
        for i, line in enumerate(lines):
            if line.startswith("from app.features."):
                last_feature_import_index = i

        import_statement = f"from app.features.{plural_name}.api.v1 import router as v1_{plural_name}_router"
        if any(import_statement in line for line in lines):
            print(f"  - Import statement already exists in {router_path}")
        elif last_feature_import_index != -1:
            lines.insert(last_feature_import_index + 1, import_statement)
        else:
            # Fallback if no feature imports are found
            after_line = "from app.core.database.deps import get_session"
            try:
                index = lines.index(after_line)
                lines.insert(index + 1, import_statement)
            except ValueError:
                lines.insert(0, import_statement)  # Add at the beginning if anchor not found

        # Add include_router
        last_include_router_index = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("v1_router.include_router("):
                last_include_router_index = i

        include_statement = f"v1_router.include_router(v1_{plural_name}_router)"
        if any(include_statement in line for line in lines):
            print(f"  - Router include statement already exists in {router_path}")
        elif last_include_router_index != -1:
            lines.insert(last_include_router_index + 1, include_statement)
        else:
            # Fallback for include router
            before_line = "router.include_router(v1_router)"
            try:
                index = lines.index(before_line)
                lines.insert(index, include_statement)
            except ValueError:
                lines.append(include_statement)  # Add at the end if anchor not found

        router_path.write_text("\n".join(lines) + "\n")
        print(f"  - Updated {router_path}")

    except FileNotFoundError:
        print(f"Warning: Could not find {router_path} to update.")
    except Exception as e:
        print(f"An error occurred while updating {router_path}: {e}")


def create_module(base_dir: str, name: str, plural: str | None):
    """
    Generates a new CRUD module.

    :param name: The name of the module in CamelCase (e.g., "Article").
    :param plural: The plural name of the module in snake_case.
    """
    class_name = name
    singular_name = to_snake_case(class_name)
    plural_name = plural if plural else pluralize(singular_name)

    base_dir = Path(__file__).parent.parent / f"src/app/features/{plural_name}"

    if base_dir.exists():
        print(f"Error: Module '{plural_name}' already exists.")
        return

    print(f"Creating module '{class_name}' in '{base_dir}'...")

    # Define file structure and content templates
    files_to_create = {
        "__init__.py": "",
        "models.py": f"""
from sqlalchemy.orm import Mapped, mapped_column

from app.base.models.mixin import Base, TimestampMixin, UUIDMixin


class {class_name}(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "{plural_name}"
    name: Mapped[str] = mapped_column()
""",
        "schemas.py": f"""
from pydantic import BaseModel, ConfigDict, Field

from app.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin


class {class_name}Create(BaseModel):
    name: str = Field(description="The name of the {singular_name}.")


class {class_name}Update(BaseModel):
    name: str | None = Field(default=None, description="The name of the {singular_name}.")


class {class_name}Read(UUIDSchemaMixin, TimestampSchemaMixin, BaseModel):
    name: str = Field(..., description="The name of the {singular_name}.")
    model_config = ConfigDict(from_attributes=True)
""",
        "repos.py": f"""
from app.base.repos.base import BaseRepository
from app.features.{plural_name}.models import {class_name}
from app.features.{plural_name}.schemas import {class_name}Create, {class_name}Update


class {class_name}Repository(BaseRepository[{class_name}, {class_name}Create, {class_name}Update]):
    model = {class_name}
""",
        "services.py": f"""
from typing import Annotated

from fastapi import Depends

from app.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from app.features.{plural_name}.models import {class_name}
from app.features.{plural_name}.repos import {class_name}Repository
from app.features.{plural_name}.schemas import {class_name}Create, {class_name}Update


class {class_name}Service(
    BaseCreateServiceMixin[{class_name}Repository, {class_name}, {class_name}Create, BaseContextKwargs],
    BaseGetMultiServiceMixin[{class_name}Repository, {class_name}, BaseContextKwargs],
    BaseGetServiceMixin[{class_name}Repository, {class_name}, BaseContextKwargs],
    BaseUpdateServiceMixin[{class_name}Repository, {class_name}, {class_name}Update, BaseContextKwargs],
    BaseDeleteServiceMixin[{class_name}Repository, {class_name}, BaseContextKwargs],
):
    def __init__(self, repo: Annotated[{class_name}Repository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> {class_name}Repository:
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs
""",
        "usecases/__init__.py": "",
        "usecases/crud.py": f"""
from typing import Annotated

from fastapi import Depends

from app.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BaseUpdateUseCase,
)
from app.features.{plural_name}.models import {class_name}
from app.features.{plural_name}.schemas import {class_name}Create, {class_name}Update
from app.features.{plural_name}.services import {class_name}Service, BaseContextKwargs


class Get{class_name}UseCase(BaseGetUseCase[{class_name}Service, {class_name}, BaseContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)


class GetMulti{class_name}UseCase(BaseGetMultiUseCase[{class_name}Service, {class_name}, BaseContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)


class Create{class_name}UseCase(BaseCreateUseCase[{class_name}Service, {class_name}, {class_name}Create, BaseContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)


class Update{class_name}UseCase(BaseUpdateUseCase[{class_name}Service, {class_name}, {class_name}Update, BaseContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)


class Delete{class_name}UseCase(BaseDeleteUseCase[{class_name}Service, {class_name}, BaseContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)
""",
        "api/__init__.py": f"""
from .v1 import router as v1_{plural_name}_router

__all__ = ["v1_{plural_name}_router"]
""",
        "api/v1.py": f"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.base.deps.params.page import PaginationParam
from app.base.exceptions.basic import NotFoundException
from app.base.schemas.delete_resp import DeleteResponse
from app.base.schemas.paginated import PaginatedList
from app.features.{plural_name}.schemas import {class_name}Create, {class_name}Read, {class_name}Update
from app.features.{plural_name}.usecases.crud import (
    Create{class_name}UseCase,
    Delete{class_name}UseCase,
    Get{class_name}UseCase,
    GetMulti{class_name}UseCase,
    Update{class_name}UseCase,
)
from app.features.auth.deps import get_current_user

router = APIRouter(prefix="/{plural_name}", tags=["{class_name}s"], dependencies=[Depends(get_current_user)])


@router.post("", status_code=status.HTTP_201_CREATED, response_model={class_name}Read)
async def create_{singular_name}(
    use_case: Annotated[Create{class_name}UseCase, Depends()],
    {singular_name}_in: {class_name}Create,
):
    return await use_case.execute({singular_name}_in)


@router.get("", response_model=PaginatedList[{class_name}Read])
async def get_{plural_name}(
    use_case: Annotated[GetMulti{class_name}UseCase, Depends()],
    pagination: PaginationParam,
):
    return await use_case.execute(**pagination)


@router.get("/{{{singular_name}_id}}", response_model={class_name}Read)
async def get_{singular_name}(
    use_case: Annotated[Get{class_name}UseCase, Depends()],
    {singular_name}_id: uuid.UUID,
):
    {singular_name} = await use_case.execute({singular_name}_id)
    if not {singular_name}:
        raise NotFoundException()
    return {singular_name}


@router.put("/{{{singular_name}_id}}", response_model={class_name}Read)
async def update_{singular_name}(
    use_case: Annotated[Update{class_name}UseCase, Depends()],
    {singular_name}_id: uuid.UUID,
    {singular_name}_in: {class_name}Update,
):
    {singular_name} = await use_case.execute({singular_name}_id, {singular_name}_in)
    if not {singular_name}:
        raise NotFoundException()
    return {singular_name}


@router.delete("/{{{singular_name}_id}}", response_model=DeleteResponse)
async def delete_{singular_name}(
    use_case: Annotated[Delete{class_name}UseCase, Depends()],
    {singular_name}_id: uuid.UUID,
):
    return await use_case.execute({singular_name}_id)
""",
    }

    # Create directories and files
    for file_path, content in files_to_create.items():
        path = base_dir / file_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.strip())
        print(f"  - Created {path}")

    print(f"\nModule '{class_name}' created successfully!")
    update_router(plural_name)

    print("\nNext steps:")
    print(f"1. Review the generated files in '{base_dir}'.")
    print("2. Add the new model to 'alembic' and run migrations.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new FastAPI CRUD module.")
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="The name of the module in CamelCase (e.g., 'Article').",
    )
    parser.add_argument(
        "--plural",
        type=str,
        help="The plural name of the module in snake_case (e.g., 'articles'). If not provided, it will be auto-generated.",
    )
    args = parser.parse_args()
    create_module(args.name, args.plural)
