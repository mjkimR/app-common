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


def update_router(plural_name: str, base_dir: Path, import_prefix: str):
    """
    Updates backend/app/router.py to include the new feature's router.
    """
    router_path = base_dir / "app/router.py"
    try:
        lines = router_path.read_text().splitlines()
        if not lines:
            print(f"Warning: {router_path} is empty. Skipping update.")
            return

        # Add import
        last_feature_import_index = -1
        for i, line in enumerate(lines):
            if line.startswith(f"from {import_prefix}."):
                last_feature_import_index = i

        import_statement = f"from {import_prefix}.{plural_name}.api.v1 import router as v1_{plural_name}_router"
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


def create_feature(
    name: str,
    plural: str | None,
    base_dir: Path | None = None,
    feature_prefix: str | None = None,
):
    """
    Generates a new CRUD feature.

    :param name: The name of the feature in CamelCase (e.g., "Article").
    :param plural: The plural name of the feature in snake_case.
    :param base_dir: The base directory of the project.
    :param feature_prefix: The prefix path for the feature directory (e.g., "app/features"). Defaults to "app/features".
    """
    if base_dir is None:
        base_dir = Path.cwd()

    class_name = name
    singular_name = to_snake_case(class_name)
    plural_name = plural if plural else pluralize(singular_name)
    prefix = feature_prefix if feature_prefix else "app/features"
    import_prefix = prefix.replace("/", ".")

    feature_dir = base_dir / f"{prefix}/{plural_name}"

    if feature_dir.exists():
        print(f"Error: Feature '{plural_name}' already exists at {feature_dir}.")
        return

    print(f"Creating feature '{class_name}' in '{feature_dir}'...")

    # Define file structure and content templates
    files_to_create = {
        "__init__.py": "",
        "models.py": f"""
from sqlalchemy.orm import Mapped, mapped_column

from app_base.base.models.mixin import Base, TimestampMixin, UUIDMixin


class {class_name}(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "{plural_name}"
    name: Mapped[str] = mapped_column()
""",
        "schemas.py": f"""
from pydantic import BaseModel, ConfigDict, Field

from app_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin


class {class_name}Base(BaseModel):
    name: str = Field(description="The name of the {singular_name}.")


class {class_name}Create({class_name}Base):
    pass


class {class_name}Put({class_name}Base):
    pass


class {class_name}Patch(BaseModel):
    name: str | None = Field(default=None, description="The name of the {singular_name}.")


class {class_name}Read(UUIDSchemaMixin, TimestampSchemaMixin, {class_name}Base):
    model_config = ConfigDict(from_attributes=True)
""",
        "repos.py": f"""
from app_base.base.repos.base import BaseRepository
from {import_prefix}.{plural_name}.models import {class_name}
from {import_prefix}.{plural_name}.schemas import {class_name}Create, {class_name}Put, {class_name}Patch


class {class_name}Repository(BaseRepository[{class_name}, {class_name}Create, {class_name}Put, {class_name}Patch]):
    model = {class_name}
""",
        "services.py": f"""
from typing import Annotated

from fastapi import Depends

from app_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from {import_prefix}.{plural_name}.models import {class_name}
from {import_prefix}.{plural_name}.repos import {class_name}Repository
from {import_prefix}.{plural_name}.schemas import {class_name}Create, {class_name}Put, {class_name}Patch


class {class_name}ContextKwargs(BaseContextKwargs):
    pass


class {class_name}Service(
    BaseCreateServiceMixin[{class_name}Repository, {class_name}, {class_name}Create, {class_name}ContextKwargs],
    BaseGetMultiServiceMixin[{class_name}Repository, {class_name}, {class_name}ContextKwargs],
    BaseGetServiceMixin[{class_name}Repository, {class_name}, {class_name}ContextKwargs],
    BaseUpdateServiceMixin[{class_name}Repository, {class_name}, {class_name}Put, {class_name}Patch, {class_name}ContextKwargs],
    BaseDeleteServiceMixin[{class_name}Repository, {class_name}, {class_name}ContextKwargs],
):
    def __init__(self, repo: Annotated[{class_name}Repository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> {class_name}Repository:
        return self._repo

    @property
    def context_model(self):
        return {class_name}ContextKwargs
""",
        "usecases/__init__.py": "",
        "usecases/crud.py": f"""
from typing import Annotated

from fastapi import Depends

from app_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
    BasePutUseCase,
)
from {import_prefix}.{plural_name}.models import {class_name}
from {import_prefix}.{plural_name}.schemas import {class_name}Create, {class_name}Put, {class_name}Patch
from {import_prefix}.{plural_name}.services import {class_name}Service, {class_name}ContextKwargs


class Get{class_name}UseCase(BaseGetUseCase[{class_name}Service, {class_name}, {class_name}ContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)


class GetMulti{class_name}UseCase(BaseGetMultiUseCase[{class_name}Service, {class_name}, {class_name}ContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)


class Create{class_name}UseCase(BaseCreateUseCase[{class_name}Service, {class_name}, {class_name}Create, {class_name}ContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)


class Patch{class_name}UseCase(BasePatchUseCase[{class_name}Service, {class_name}, {class_name}Put, {class_name}Patch, {class_name}ContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)


class Put{class_name}UseCase(BasePutUseCase[{class_name}Service, {class_name}, {class_name}Put, {class_name}Patch, {class_name}ContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)


class Delete{class_name}UseCase(BaseDeleteUseCase[{class_name}Service, {class_name}, {class_name}ContextKwargs]):
    def __init__(self, service: Annotated[{class_name}Service, Depends()]) -> None:
        super().__init__(service)
""",
        "api/__init__.py": f"""
from .v1 import router as v1_{plural_name}_router

__all__ = ["v1_{plural_name}_router"]
""",
        "api/v1.py": f"""
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app_base.base.deps.params.page import PaginationParam
from app_base.base.exceptions.basic import NotFoundException
from app_base.base.repos.query_options import ListQueryOptions
from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.schemas.paginated import PaginatedList
from {import_prefix}.{plural_name}.schemas import {class_name}Create, {class_name}Read, {class_name}Patch, {class_name}Put
from {import_prefix}.{plural_name}.usecases.crud import (
    Create{class_name}UseCase,
    Delete{class_name}UseCase,
    Get{class_name}UseCase,
    GetMulti{class_name}UseCase,
    Patch{class_name}UseCase,
    Put{class_name}UseCase,
)

router = APIRouter(prefix="/{plural_name}", tags=["{class_name}"], dependencies=[])


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
    query_options = ListQueryOptions(offset=pagination.offset, limit=pagination.limit)
    return await use_case.execute(query_options=query_options)


@router.get("/{{{singular_name}_id}}", response_model={class_name}Read)
async def get_{singular_name}(
    use_case: Annotated[Get{class_name}UseCase, Depends()],
    {singular_name}_id: UUID,
):
    {singular_name} = await use_case.execute({singular_name}_id)
    if not {singular_name}:
        raise NotFoundException()
    return {singular_name}


@router.patch("/{{{singular_name}_id}}", response_model={class_name}Read)
async def patch_{singular_name}(
    use_case: Annotated[Patch{class_name}UseCase, Depends()],
    {singular_name}_id: UUID,
    {singular_name}_in: {class_name}Patch,
):
    {singular_name} = await use_case.execute({singular_name}_id, {singular_name}_in)
    if not {singular_name}:
        raise NotFoundException()
    return {singular_name}


@router.put("/{{{singular_name}_id}}", response_model={class_name}Read)
async def put_{singular_name}(
    use_case: Annotated[Put{class_name}UseCase, Depends()],
    {singular_name}_id: UUID,
    {singular_name}_in: {class_name}Put,
):
    {singular_name} = await use_case.execute({singular_name}_id, {singular_name}_in)
    if not {singular_name}:
        raise NotFoundException()
    return {singular_name}


@router.delete("/{{{singular_name}_id}}", response_model=DeleteResponse)
async def delete_{singular_name}(
    use_case: Annotated[Delete{class_name}UseCase, Depends()],
    {singular_name}_id: UUID,
):
    return await use_case.execute({singular_name}_id)
""",
    }

    # Create directories and files
    for file_path, content in files_to_create.items():
        path = feature_dir / file_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.strip())
        print(f"  - Created {path}")

    print(f"\nFeature '{class_name}' created successfully!")
    update_router(plural_name, base_dir, import_prefix)

    print("\nNext steps:")
    print(f"1. Review the generated files in '{feature_dir}'.")
    print("2. Add the new model to 'alembic' and run migrations.")
