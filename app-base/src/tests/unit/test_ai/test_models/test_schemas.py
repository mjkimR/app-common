import pytest
from pydantic import ValidationError

from app_base.ai.models.schemas import (
    AIModelAliasItem,
    AICatalogItem,
    AIModelGroupItem,
    AIModelItem,
    AIModelParamSpec,
    AIModelType,
)


def test_ai_model_type_enum():
    assert AIModelType.LLM == "llm"
    assert AIModelType.EMBEDDING == "text-embedding"
    assert AIModelType.STT == "stt"
    assert AIModelType.TTS == "tts"
    assert AIModelType.IMAGE_GEN == "image-generation"


def test_ai_catalog_item_creation():
    item = AICatalogItem(name="test-model", kind="model", type=AIModelType.LLM)
    assert item.name == "test-model"
    assert item.kind == "model"
    assert item.type == AIModelType.LLM
    assert item.help is None
    assert item.provider is None

    item_with_all_fields = AICatalogItem(
        name="test-alias",
        kind="alias",
        type=AIModelType.EMBEDDING,
        help="A test alias",
        provider="alias",
    )
    assert item_with_all_fields.name == "test-alias"
    assert item_with_all_fields.kind == "alias"
    assert item_with_all_fields.type == AIModelType.EMBEDDING
    assert item_with_all_fields.help == "A test alias"
    assert item_with_all_fields.provider == "alias"


def test_ai_model_param_spec_defaults():
    spec = AIModelParamSpec()
    assert spec.exclude == []
    assert spec.map == {}

    spec_with_values = AIModelParamSpec(exclude=["temp"], map={"api_key": "key"})
    assert spec_with_values.exclude == ["temp"]
    assert spec_with_values.map == {"api_key": "key"}


def test_ai_model_item_creation():
    model_item = AIModelItem(name="gpt-4", type=AIModelType.LLM, provider="openai")
    assert model_item.name == "gpt-4"
    assert model_item.type == AIModelType.LLM
    assert model_item.provider == "openai"
    assert model_item.kind == "model"
    assert model_item.args == {}
    assert model_item.fallbacks == []
    assert model_item.dimension is None

    model_item_full = AIModelItem(
        name="embedding-model",
        type=AIModelType.EMBEDDING,
        provider="google",
        help="Google Embedding Model",
        args={"api_key": "abc"},
        fallbacks=["backup-embedding"],
        dimension=768,
    )
    assert model_item_full.name == "embedding-model"
    assert model_item_full.type == AIModelType.EMBEDDING
    assert model_item_full.provider == "google"
    assert model_item_full.help == "Google Embedding Model"
    assert model_item_full.args == {"api_key": "abc"}
    assert model_item_full.fallbacks == ["backup-embedding"]
    assert model_item_full.dimension == 768


def test_ai_model_item_to_catalog_item():
    model_item = AIModelItem(name="test-llm", type=AIModelType.LLM, provider="test-provider", help="A test LLM")
    catalog_item = model_item.to_catalog_item()
    assert isinstance(catalog_item, AICatalogItem)
    assert catalog_item.name == "test-llm"
    assert catalog_item.kind == "model"
    assert catalog_item.type == AIModelType.LLM
    assert catalog_item.help == "A test LLM"
    assert catalog_item.provider == "test-provider"


def test_ai_model_item_get_mapped_args():
    model_item = AIModelItem(
        name="test-model",
        type=AIModelType.LLM,
        provider="test",
        args={"api_key": "123", "temperature": 0.7, "model_name": "gpt"},
        param_spec=AIModelParamSpec(exclude=["model_name"], map={"api_key": "key"}),
    )
    mapped_args = model_item.get_mapped_args()
    assert "model_name" not in mapped_args
    assert "api_key" not in mapped_args  # Should be mapped to 'key'
    assert mapped_args["key"] == "123"
    assert mapped_args["temperature"] == 0.7

    model_item_no_spec = AIModelItem(name="test-model", type=AIModelType.LLM, provider="test", args={"param1": "val1"})
    assert model_item_no_spec.get_mapped_args() == {"param1": "val1"}


def test_ai_model_alias_item_creation():
    alias_item = AIModelAliasItem(name="fast-llm", type=AIModelType.LLM, target="gpt-3.5")
    assert alias_item.name == "fast-llm"
    assert alias_item.type == AIModelType.LLM
    assert alias_item.target == "gpt-3.5"
    assert alias_item.kind == "alias"
    assert alias_item.help is None
    assert alias_item.fallbacks == []

    alias_item_full = AIModelAliasItem(
        name="default-embedding",
        type=AIModelType.EMBEDDING,
        target="openai-embed",
        help="Default embedding alias",
        fallbacks=["google-embed"],
    )
    assert alias_item_full.name == "default-embedding"
    assert alias_item_full.type == AIModelType.EMBEDDING
    assert alias_item_full.target == "openai-embed"
    assert alias_item_full.help == "Default embedding alias"
    assert alias_item_full.fallbacks == ["google-embed"]


def test_ai_model_alias_item_to_catalog_item():
    alias_item = AIModelAliasItem(name="short-llm", type=AIModelType.LLM, target="gpt-3.5", help="A short LLM")
    catalog_item = alias_item.to_catalog_item()
    assert isinstance(catalog_item, AICatalogItem)
    assert catalog_item.name == "short-llm"
    assert catalog_item.kind == "alias"
    assert catalog_item.type == AIModelType.LLM
    assert catalog_item.help == "A short LLM (Target: gpt-3.5)"
    assert catalog_item.provider == "alias"

    alias_item_no_help = AIModelAliasItem(name="no-help", type=AIModelType.LLM, target="model-a")
    catalog_item_no_help = alias_item_no_help.to_catalog_item()
    assert catalog_item_no_help.help == "Model Alias (Target: model-a)"


def test_ai_model_group_item_from_data():
    # Setup some catalog items for testing from_data
    llm_model_1 = AIModelItem(name="llm-1", type=AIModelType.LLM, provider="p1")
    llm_model_2 = AIModelItem(name="llm-2", type=AIModelType.LLM, provider="p2")
    embed_model_1 = AIModelItem(name="embed-1", type=AIModelType.EMBEDDING, provider="p3")

    llm_alias_1 = AIModelAliasItem(name="alias-llm", type=AIModelType.LLM, target="llm-1")

    catalogs = {
        "llm-1": llm_model_1.to_catalog_item(),
        "llm-2": llm_model_2.to_catalog_item(),
        "embed-1": embed_model_1.to_catalog_item(),
        "alias-llm": llm_alias_1.to_catalog_item(),
    }

    # Test valid group creation with default specified
    group_data_with_default = {
        "name": "llm-group",
        "type": AIModelType.LLM,
        "members": ["llm-1", "alias-llm", "llm-2"],
        "default": "alias-llm",
    }
    group = AIModelGroupItem.from_data(group_data_with_default, catalogs)
    assert group.name == "llm-group"
    assert group.type == AIModelType.LLM
    assert len(group.members) == 3
    assert group.default == "alias-llm"
    assert any(m.name == "llm-1" for m in group.members)
    assert any(m.name == "alias-llm" for m in group.members)
    assert any(m.name == "llm-2" for m in group.members)

    # Test valid group creation without default (first member should be default)
    group_data_no_default = {
        "name": "another-llm-group",
        "type": AIModelType.LLM,
        "members": ["llm-2", "llm-1"],
    }
    group_no_default = AIModelGroupItem.from_data(group_data_no_default, catalogs)
    assert group_no_default.name == "another-llm-group"
    assert group_no_default.type == AIModelType.LLM
    assert len(group_no_default.members) == 2
    assert group_no_default.default == "llm-2"  # First member becomes default

    # Test cases for validation errors
    # Missing name
    with pytest.raises(ValueError, match="Model group is missing a 'name' field."):
        AIModelGroupItem.from_data({"type": AIModelType.LLM, "members": ["llm-1"]}, catalogs)

    # Missing type
    with pytest.raises(ValueError, match="Model group 'test-group' is missing a 'type' field."):
        AIModelGroupItem.from_data({"name": "test-group", "members": ["llm-1"]}, catalogs)

    # Empty members
    with pytest.raises(ValueError, match="Model group 'test-group' must have at least one member."):
        AIModelGroupItem.from_data({"name": "test-group", "type": AIModelType.LLM, "members": []}, catalogs)

    # Unknown member
    with pytest.raises(ValueError, match="Model group 'test-group' has unknown member 'non-existent'."):
        AIModelGroupItem.from_data(
            {"name": "test-group", "type": AIModelType.LLM, "members": ["non-existent"]}, catalogs
        )

    # Type mismatch for member
    with pytest.raises(
        ValueError,
        match="Model group 'test-group' has member 'embed-1' with type \(text-embedding\) "
        "that does not match group type \\(AIModelType.LLM\\).",
    ):
        AIModelGroupItem.from_data({"name": "test-group", "type": AIModelType.LLM, "members": ["embed-1"]}, catalogs)

    # Default not in members
    with pytest.raises(
        ValueError, match="Model group 'test-group' has default 'llm-3' which is not in its members list."
    ):
        AIModelGroupItem.from_data(
            {"name": "test-group", "type": AIModelType.LLM, "members": ["llm-1"], "default": "llm-3"}, catalogs
        )
