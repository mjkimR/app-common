from app_base.base.repos.query_options import ListQueryOptions
from app_base.base.usecases.crud import (
    BaseCreateUseCase,
    BaseDeleteUseCase,
    BaseGetMultiUseCase,
    BaseGetUseCase,
    BasePatchUseCase,
)

from tests.integrate.test_base.test_services.test_item_lifecycle import (
    ItemCreate,
    ItemRepository,
    ItemService,
    ItemUpdate,
)


class CreateItemUseCase(BaseCreateUseCase):
    def __init__(self):
        super().__init__(service=ItemService(ItemRepository()))


class GetItemUseCase(BaseGetUseCase):
    def __init__(self):
        super().__init__(service=ItemService(ItemRepository()))


class PatchItemUseCase(BasePatchUseCase):
    def __init__(self):
        super().__init__(service=ItemService(ItemRepository()))


class DeleteItemUseCase(BaseDeleteUseCase):
    def __init__(self):
        super().__init__(service=ItemService(ItemRepository()))


class GetMultiItemUseCase(BaseGetMultiUseCase):
    def __init__(self):
        super().__init__(service=ItemService(ItemRepository()))


async def test_usecase_lifecycle(session):
    import uuid
    # Since AsyncTransaction manages its own session, we don't pass the fixture session directly
    # The transaction will automatically pick up the patched test db engine.

    user_id = uuid.uuid4()
    context = {"user_id": user_id}

    # 1. Create
    create_uc = CreateItemUseCase()
    item = await create_uc.execute(ItemCreate(name="UseCase Test", description="Desc"), context=context)
    assert item.id is not None
    assert item.name == "UseCase Test"

    # 2. Get
    get_uc = GetItemUseCase()
    fetched = await get_uc.execute(item.id, context=context)
    assert fetched is not None
    assert fetched.id == item.id

    # 3. Patch
    patch_uc = PatchItemUseCase()
    updated = await patch_uc.execute(item.id, ItemUpdate(name="UseCase Patched"), context=context)
    assert updated is not None
    assert updated.name == "UseCase Patched"

    # 4. Get Multi
    multi_uc = GetMultiItemUseCase()
    items = await multi_uc.execute(query_options=ListQueryOptions(offset=0, limit=10), context=context)
    assert items.total_count == 1
    assert items.items[0].id == item.id

    # 5. Delete
    delete_uc = DeleteItemUseCase()
    resp = await delete_uc.execute(item.id, context=context)
    assert resp.success is True

    # 6. Verify Deletion
    not_found = await get_uc.execute(item.id, context=context)
    assert not_found is None
