from .test_services.test_item_lifecycle import (
    ItemCreate,
    ItemRepository,
)


async def test_repository_create_multi(session):
    repo = ItemRepository()

    items_to_create = [ItemCreate(name=f"Bulk Item {i}") for i in range(5)]

    extra_fields = [{"description": f"Desc {i}"} for i in range(5)]

    created_items = await repo.create_multi(session, items_to_create, extra_fields_list=extra_fields)

    assert len(created_items) == 5
    for i, item in enumerate(created_items):
        assert item.id is not None
        assert item.name == f"Bulk Item {i}"
        assert item.description == f"Desc {i}"


async def test_repository_delete_by_pk_multi(session):
    repo = ItemRepository()

    # Create 3 items
    items_to_create = [ItemCreate(name=f"To Delete {i}") for i in range(3)]
    created_items = await repo.create_multi(session, items_to_create)
    pks = [item.id for item in created_items]

    # Delete them in bulk
    deleted_count = await repo.delete_by_pk_multi(session, pks)
    assert deleted_count == 3

    # Verify they are gone
    remaining = await repo.get_all(session)
    assert len(remaining) == 0


async def test_repository_get_all(session):
    repo = ItemRepository()
    items_to_create = [ItemCreate(name=f"Get All {i}") for i in range(2)]
    await repo.create_multi(session, items_to_create)

    all_items = await repo.get_all(session)
    assert len(all_items) == 2
