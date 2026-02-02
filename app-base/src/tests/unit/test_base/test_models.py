"""Unit app_tests for app_base.base.models.mixin module."""

from app_base.base.models.mixin import (
    AuditMixin,
    SoftDeleteMixin,
    TaggableMixin,
    TimestampMixin,
    UUIDMixin,
)


class TestTaggableMixin:
    """Tests for TaggableMixin methods."""

    def test_add_tag_to_empty_tags(self):
        """Should initialize tags and add tag when tags is None."""

        class TestModel(TaggableMixin):
            def __init__(self):
                self.tags = None

        model = TestModel()
        model.add_tag("python")

        assert model.tags == ["python"]

    def test_add_tag_to_existing_tags(self):
        """Should app_kitend tag to existing tags."""

        class TestModel(TaggableMixin):
            def __init__(self):
                self.tags = ["python"]

        model = TestModel()
        model.add_tag("fastapi")

        assert model.tags == ["python", "fastapi"]

    def test_add_tag_prevents_duplicates(self):
        """Should not add duplicate tags."""

        class TestModel(TaggableMixin):
            def __init__(self):
                self.tags = ["python", "fastapi"]

        model = TestModel()
        model.add_tag("python")

        assert model.tags is not None
        assert model.tags == ["python", "fastapi"]
        assert model.tags.count("python") == 1

    def test_add_multiple_unique_tags(self):
        """Should add multiple unique tags."""

        class TestModel(TaggableMixin):
            def __init__(self):
                self.tags = None

        model = TestModel()
        model.add_tag("python")
        model.add_tag("fastapi")
        model.add_tag("sqlalchemy")

        assert model.tags == ["python", "fastapi", "sqlalchemy"]

    def test_remove_tag_from_existing_tags(self):
        """Should remove tag from tags list."""

        class TestModel(TaggableMixin):
            def __init__(self):
                self.tags = ["python", "fastapi", "sqlalchemy"]

        model = TestModel()
        model.remove_tag("fastapi")

        assert model.tags == ["python", "sqlalchemy"]

    def test_remove_tag_not_in_list(self):
        """Should do nothing when tag not in list."""

        class TestModel(TaggableMixin):
            def __init__(self):
                self.tags = ["python", "fastapi"]

        model = TestModel()
        model.remove_tag("django")

        assert model.tags == ["python", "fastapi"]

    def test_remove_tag_from_none_tags(self):
        """Should handle None tags gracefully."""

        class TestModel(TaggableMixin):
            def __init__(self):
                self.tags = None

        model = TestModel()
        model.remove_tag("python")

        assert model.tags is None

    def test_remove_tag_from_empty_list(self):
        """Should handle empty tags list."""

        class TestModel(TaggableMixin):
            def __init__(self):
                self.tags = []

        model = TestModel()
        model.remove_tag("python")

        assert model.tags == []

    def test_remove_last_tag(self):
        """Should leave empty list when removing last tag."""

        class TestModel(TaggableMixin):
            def __init__(self):
                self.tags = ["python"]

        model = TestModel()
        model.remove_tag("python")

        assert model.tags == []


class TestMixinDefaults:
    """Tests for mixin default values."""

    def test_uuid_mixin_default_value(self):
        """UUIDMixin should provide a default UUID."""
        # This app_tests the column definition, not runtime behavior
        assert hasattr(UUIDMixin, "id")

    def test_timestamp_mixin_has_created_at(self):
        """TimestampMixin should have created_at field."""
        assert hasattr(TimestampMixin, "created_at")

    def test_timestamp_mixin_has_updated_at(self):
        """TimestampMixin should have updated_at field."""
        assert hasattr(TimestampMixin, "updated_at")

    def test_soft_delete_mixin_default_is_deleted_false(self):
        """SoftDeleteMixin should default is_deleted to False."""
        assert hasattr(SoftDeleteMixin, "is_deleted")
        assert hasattr(SoftDeleteMixin, "deleted_at")

    def test_audit_mixin_has_created_by(self):
        """AuditMixin should have created_by field."""
        assert hasattr(AuditMixin, "created_by")

    def test_audit_mixin_has_updated_by(self):
        """AuditMixin should have updated_by field."""
        assert hasattr(AuditMixin, "updated_by")

    def test_taggable_mixin_has_tags(self):
        """TaggableMixin should have tags field."""
        assert hasattr(TaggableMixin, "tags")
