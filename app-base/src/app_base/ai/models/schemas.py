from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AIModelType(str, Enum):
    LLM = "llm"
    EMBEDDING = "text-embedding"
    STT = "stt"
    TTS = "tts"
    IMAGE_GEN = "image-generation"


class AICatalogItem(BaseModel):
    name: str = Field(..., description="The name of the model or alias")
    kind: Literal["model", "alias"] = Field(..., description="Indicates whether this is a model or alias")
    type: AIModelType = Field(..., description="The type of the model")
    help: str | None = Field(default=None, description="Description of the model or alias")
    provider: str | None = Field(
        default=None,
        description="The provider of the model (provider is 'alias' for aliases)",
    )


class AIModelParamSpec(BaseModel):
    exclude: list[str] = Field(default_factory=list, description="List of parameter names to exclude")
    map: dict[str, str] = Field(default_factory=dict, description="Mapping of parameter names")


class AIModelItem(BaseModel):
    name: str = Field(..., description="The name of the model")
    type: AIModelType = Field(..., description="The type of the model")
    provider: str = Field(..., description="The provider of the model")
    help: str | None = Field(default=None, description="Description of the model")
    args: dict[str, Any] = Field(default_factory=dict, description="Arguments for model initialization")
    fallbacks: list[str] = Field(default_factory=list, description="List of fallback model/alias names")
    kind: Literal["model"] = Field(default="model", description="Indicates this is a model item")

    param_spec: AIModelParamSpec = Field(
        default_factory=AIModelParamSpec,
        description="Specification for parameter exclusions and mappings",
    )

    # For embedding models, optional dimension info
    dimension: int | None = Field(default=None, description="Embedding dimension size (e.g., 1536, 768)")

    def to_catalog_item(self) -> AICatalogItem:
        return AICatalogItem(
            name=self.name,
            kind="model",
            type=self.type,
            help=self.help,
            provider=self.provider,
        )

    def get_mapped_args(self) -> dict[str, Any]:
        mapped_args = {}
        for key, value in self.args.items():
            if key in self.param_spec.exclude:
                continue
            mapped_key = self.param_spec.map.get(key)
            mapped_args[mapped_key] = value
        return mapped_args


class AIModelAliasItem(BaseModel):
    name: str = Field(..., description="The name of the model alias")
    type: AIModelType = Field(..., description="The type of models in this alias")
    target: str = Field(..., description="The target model name for this alias")
    help: str | None = Field(default=None, description="Description of the model alias")
    fallbacks: list[str] = Field(default_factory=list, description="List of fallback model/alias names")
    kind: Literal["alias"] = Field(default="alias", description="Indicates this is an alias item")

    def to_catalog_item(self) -> AICatalogItem:
        base_desc = self.help or "Model Alias"
        full_desc = f"{base_desc} (Target: {self.target})"

        return AICatalogItem(
            name=self.name,
            type=self.type,
            provider="alias",
            help=full_desc,
            kind="alias",
        )


class AIModelGroupItem(BaseModel):
    name: str = Field(..., description="The name of the model group")
    type: AIModelType = Field(..., description="The type of models in this group")
    members: list[AICatalogItem] = Field(..., description="List of models/aliases in this group")
    default: str = Field(..., description="The default model/alias name for this group")

    @classmethod
    def from_data(cls, data: dict[str, Any], catalogs: dict[str, AICatalogItem]) -> "AIModelGroupItem":
        _name = data.get("name")
        _type = data.get("type")
        _member_names = data.get("members", [])
        _default = data.get("default")

        # Basic validations
        if not _name:
            raise ValueError("Model group is missing a 'name' field.")
        if not _type:
            raise ValueError(f"Model group '{_name}' is missing a 'type' field.")
        if len(_member_names) == 0:
            raise ValueError(f"Model group '{_name}' must have at least one member.")
        if not _default:
            _default = _member_names[0]

        # Validate members
        for _member_name in _member_names:
            if _member_name not in catalogs:
                raise ValueError(f"Model group '{_name}' has unknown member '{_member_name}'.")
            if catalogs[_member_name].type != _type:
                raise ValueError(
                    f"Model group '{_name}' has member '{_member_name}' with type "
                    f"({catalogs[_member_name].type.value}) that does not match group type ({_type})."
                )

        # Validate default
        if _default not in _member_names:
            raise ValueError(f"Model group '{_name}' has default '{_default}' which is not in its members list.")

        return cls(
            name=_name,
            type=_type,
            members=[catalogs[m] for m in _member_names],
            default=_default,
        )
