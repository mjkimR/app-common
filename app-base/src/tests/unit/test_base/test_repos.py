"""Unit app_tests for app_base.base.repos.base module."""

import uuid
from unittest.mock import MagicMock

import pytest

from app_base.base.schemas.paginated import PaginatedList


class TestBaseRepositoryPrimaryKeys:
    """Tests for primary key handling in BaseRepository."""

    def test_get_primary_keys_returns_primary_key_columns(self, mock_repository):
        """Should correctly identify primary key columns from model."""
        pk_columns = mock_repository._primary_keys
        assert len(pk_columns) == 1
        assert pk_columns[0].key == "id"

    def test_get_primary_key_filters_single_value(self, mock_repository, sample_uuid):
        """Should create filter for single primary key value."""
        filters = mock_repository._get_primary_key_filters(sample_uuid)
        assert len(filters) == 1

    def test_get_primary_key_filters_string_pk(self, mock_repository):
        """Should handle string primary key (not as sequence)."""
        # String should be treated as single value, not sequence of characters
        str_uuid = "12345678-1234-5678-1234-567812345678"
        filters = mock_repository._get_primary_key_filters(str_uuid)
        assert len(filters) == 1

    def test_get_primary_key_filters_sequence(self, mock_repository, sample_uuid):
        """Should handle sequence of primary key values."""
        filters = mock_repository._get_primary_key_filters([sample_uuid])
        assert len(filters) == 1

    def test_get_primary_key_filters_mismatched_count_raises_error(self, mock_repository, sample_uuid):
        """Should raise error when PK count doesn't match."""
        with pytest.raises(ValueError, match="Incorrect number of primary key values"):
            mock_repository._get_primary_key_filters([sample_uuid, sample_uuid])


class TestBaseRepositorySelect:
    """Tests for _select method."""

    def test_select_without_conditions(self, mock_repository):
        """Should build select statement without where/order_by."""
        stmt = mock_repository._select()
        assert stmt is not None

    def test_select_with_single_where_condition(self, mock_repository):
        """Should app_kitly single where condition."""
        from src.tests.test_app_base.unit.test_base.conftest import MockModel

        condition = MockModel.name == "test"
        stmt = mock_repository._select(where=condition)
        assert stmt is not None

    def test_select_with_sequence_where_conditions(self, mock_repository):
        """Should app_kitly multiple where conditions from sequence."""
        from src.tests.test_app_base.unit.test_base.conftest import MockModel

        conditions = [MockModel.name == "test", MockModel.description == "desc"]
        stmt = mock_repository._select(where=conditions)
        assert stmt is not None

    def test_select_with_empty_sequence_where(self, mock_repository):
        """Should handle empty sequence for where conditions."""
        stmt = mock_repository._select(where=[])
        assert stmt is not None

    def test_select_with_order_by(self, mock_repository):
        """Should app_kitly order_by conditions."""
        from src.tests.test_app_base.unit.test_base.conftest import MockModel

        stmt = mock_repository._select(order_by=[MockModel.name.asc()])
        assert stmt is not None

    def test_select_default_order_by_updated_at(self, mock_repository):
        """Should use default order_by (updated_at desc) when not specified."""
        stmt = mock_repository._select(order_by=())
        # The default order should be app_kitlied (updated_at desc)
        assert stmt is not None


class TestBaseRepositoryGet:
    """Tests for get operations."""

    @pytest.mark.asyncio
    async def test_get_returns_model_when_found(self, mock_repository, mock_async_session, mock_model):
        """Should return model when found."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_async_session.execute.return_value = mock_result

        result = await mock_repository.get(mock_async_session)

        assert result == mock_model
        mock_async_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, mock_repository, mock_async_session):
        """Should return None when no model found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_async_session.execute.return_value = mock_result

        result = await mock_repository.get(mock_async_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_pk_returns_model(self, mock_repository, mock_async_session, mock_model, sample_uuid):
        """Should return model by primary key."""
        mock_async_session.get.return_value = mock_model

        result = await mock_repository.get_by_pk(mock_async_session, sample_uuid)

        assert result == mock_model
        mock_async_session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_pk_with_sequence_pk(self, mock_repository, mock_async_session, mock_model, sample_uuid):
        """Should handle sequence of PK values."""
        mock_async_session.get.return_value = mock_model

        result = await mock_repository.get_by_pk(mock_async_session, [sample_uuid])

        assert result == mock_model


class TestBaseRepositoryExists:
    """Tests for exists method."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_when_found(self, mock_repository, mock_async_session):
        """Should return True when record exists."""
        from src.tests.test_app_base.unit.test_base.conftest import MockModel

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        mock_async_session.execute.return_value = mock_result

        # Provide a proper where condition
        result = await mock_repository.exists(mock_async_session, where=MockModel.name == "test")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_when_not_found(self, mock_repository, mock_async_session):
        """Should return False when record doesn't exist."""
        from src.tests.test_app_base.unit.test_base.conftest import MockModel

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_async_session.execute.return_value = mock_result

        result = await mock_repository.exists(mock_async_session, where=MockModel.name == "test")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_with_no_where_clause(self, mock_repository, mock_async_session):
        """Should handle None where clause (check any existence)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        mock_async_session.execute.return_value = mock_result

        # Pass None explicitly to check existence of any record
        result = await mock_repository.exists(mock_async_session, where=None)

        assert result is True


class TestBaseRepositoryCreate:
    """Tests for create operation."""

    @pytest.mark.asyncio
    async def test_create_adds_and_flushes(self, mock_repository, mock_async_session, mock_create_schema):
        """Should add model to session and flush."""
        await mock_repository.create(mock_async_session, mock_create_schema)

        mock_async_session.add.assert_called_once()
        mock_async_session.flush.assert_called_once()
        mock_async_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_extra_fields(self, mock_repository, mock_async_session, mock_create_schema):
        """Should app_kitly extra fields to created model."""
        extra_id = uuid.uuid4()

        await mock_repository.create(mock_async_session, mock_create_schema, id=extra_id)

        # Verify add was called with a model that has the extra field
        call_args = mock_async_session.add.call_args
        added_model = call_args[0][0]
        assert added_model.id == extra_id


class TestBaseRepositoryGetMulti:
    """Tests for get_multi (pagination) operations."""

    @pytest.mark.asyncio
    async def test_get_multi_returns_paginated_list(self, mock_repository, mock_async_session, mock_model):
        """Should return PaginatedList with items."""
        # Mock count query
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        # Mock data query
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [mock_model]
        data_result.scalars.return_value = scalars_mock

        mock_async_session.execute.side_effect = [count_result, data_result]

        result = await mock_repository.get_multi(mock_async_session, offset=0, limit=10)

        assert isinstance(result, PaginatedList)
        assert result.total_count == 1
        assert len(result.items) == 1
        assert result.offset == 0
        assert result.limit == 10

    @pytest.mark.asyncio
    async def test_get_multi_negative_limit_raises_error(self, mock_repository, mock_async_session):
        """Should raise ValueError for negative limit."""
        with pytest.raises(ValueError, match="Limit must be non-negative"):
            await mock_repository.get_multi(mock_async_session, limit=-1)

    @pytest.mark.asyncio
    async def test_get_multi_negative_offset_raises_error(self, mock_repository, mock_async_session):
        """Should raise ValueError for negative offset."""
        with pytest.raises(ValueError, match="Offset must be non-negative"):
            await mock_repository.get_multi(mock_async_session, offset=-1)

    @pytest.mark.asyncio
    async def test_get_multi_with_none_limit(self, mock_repository, mock_async_session, mock_model):
        """Should handle None limit (no limit)."""
        count_result = MagicMock()
        count_result.scalar_one.return_value = 100

        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [mock_model] * 100
        data_result.scalars.return_value = scalars_mock

        mock_async_session.execute.side_effect = [count_result, data_result]

        result = await mock_repository.get_multi(mock_async_session, offset=0, limit=None)

        assert result.limit is None
        assert len(result.items) == 100


class TestBaseRepositoryUpdate:
    """Tests for update operations."""

    @pytest.mark.asyncio
    async def test_update_by_pk_with_schema(self, mock_repository, mock_async_session, mock_model, sample_uuid):
        """Should update model with schema data."""
        from src.tests.test_app_base.unit.test_base.conftest import MockUpdateSchema

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_async_session.execute.return_value = mock_result

        # Mock get for return
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = mock_model
        mock_async_session.execute.side_effect = [mock_result, get_result]

        update_schema = MockUpdateSchema(name="Updated Name")
        result = await mock_repository.update_by_pk(mock_async_session, sample_uuid, update_schema)

        assert result is not None
        mock_async_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_by_pk_with_dict(self, mock_repository, mock_async_session, mock_model, sample_uuid):
        """Should update model with dict data."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_async_session.execute.return_value = mock_result

        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = mock_model
        mock_async_session.execute.side_effect = [mock_result, get_result]

        result = await mock_repository.update_by_pk(mock_async_session, sample_uuid, {"name": "Updated"})

        assert result is not None

    @pytest.mark.asyncio
    async def test_update_by_pk_empty_data_raises_error(self, mock_repository, mock_async_session, sample_uuid):
        """Should raise error when update data is empty."""
        from src.tests.test_app_base.unit.test_base.conftest import MockUpdateSchema

        # Schema with no fields set
        update_schema = MockUpdateSchema()

        with pytest.raises(ValueError, match="Update data cannot be empty"):
            await mock_repository.update_by_pk(mock_async_session, sample_uuid, update_schema)

    @pytest.mark.asyncio
    async def test_update_by_pk_extra_fields_raises_error(self, mock_repository, mock_async_session, sample_uuid):
        """Should raise error when extra fields not in model are provided."""
        with pytest.raises(ValueError, match="Extra fields provided"):
            await mock_repository.update_by_pk(mock_async_session, sample_uuid, {"nonexistent_field": "value"})

    @pytest.mark.asyncio
    async def test_update_by_pk_returns_none_when_not_found(self, mock_repository, mock_async_session, sample_uuid):
        """Should return None when record not found."""
        from src.tests.test_app_base.unit.test_base.conftest import MockUpdateSchema

        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_async_session.execute.return_value = mock_result

        update_schema = MockUpdateSchema(name="Updated")
        result = await mock_repository.update_by_pk(mock_async_session, sample_uuid, update_schema)

        assert result is None


class TestBaseRepositoryDelete:
    """Tests for delete operations."""

    @pytest.mark.asyncio
    async def test_delete_by_pk_hard_delete(self, mock_repository, mock_async_session, sample_uuid):
        """Should perform hard delete by default."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_async_session.execute.return_value = mock_result

        result = await mock_repository.delete_by_pk(mock_async_session, sample_uuid)

        assert result is True
        mock_async_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_pk_returns_false_when_not_found(self, mock_repository, mock_async_session, sample_uuid):
        """Should return False when record not found."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_async_session.execute.return_value = mock_result

        result = await mock_repository.delete_by_pk(mock_async_session, sample_uuid)

        assert result is False
        mock_async_session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_by_pk_soft_delete(self, mock_soft_delete_repository, mock_async_session, sample_uuid):
        """Should perform soft delete when flag is True."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_async_session.execute.return_value = mock_result

        result = await mock_soft_delete_repository.delete_by_pk(mock_async_session, sample_uuid, soft_delete=True)

        assert result is True
        mock_async_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_pk_soft_delete_without_column_raises_error(
        self, mock_repository, mock_async_session, sample_uuid
    ):
        """Should raise error when soft delete requested but model lacks is_deleted column."""
        with pytest.raises(ValueError, match="Soft delete requires"):
            await mock_repository.delete_by_pk(mock_async_session, sample_uuid, soft_delete=True)


class TestBaseRepositoryModelName:
    """Tests for model_name property."""

    def test_model_name_returns_class_name(self, mock_repository):
        """Should return the model class name."""
        assert mock_repository.model_name() == "MockModel"
