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
    name: str = Field(..., description="The name of the model, route, alias, or collection")
    kind: Literal["model", "route", "alias", "collection"] = Field(..., description="The catalog item kind")
    type: AIModelType = Field(..., description="The model capability type")
    help: str | None = Field(default=None, description="Description of the catalog item")
    target: str | None = Field(default=None, description="Resolved target for aliases")


class AIModelItem(BaseModel):
    name: str = Field(..., description="The public name used to call this LiteLLM model")
    type: AIModelType = Field(..., description="The model capability type")
    litellm_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters passed to LiteLLM for this deployment",
    )
    model_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional LiteLLM model metadata",
    )
    help: str | None = Field(default=None, description="Description of the model")
    kind: Literal["model"] = "model"

    def to_catalog_item(self) -> AICatalogItem:
        return AICatalogItem(name=self.name, kind="model", type=self.type, help=self.help)

    def to_router_model(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "model_name": self.name,
            "litellm_params": dict(self.litellm_params),
        }
        if self.model_info:
            item["model_info"] = dict(self.model_info)
        return item

    @property
    def dimension(self) -> int | None:
        value = self.model_info.get("dimension")
        return int(value) if value is not None else None


class AIRouteDeploymentItem(BaseModel):
    litellm_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters passed to LiteLLM for this deployment",
    )
    model_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional LiteLLM model metadata for this deployment",
    )
    tpm: int | None = Field(default=None, description="Optional token-per-minute limit")
    rpm: int | None = Field(default=None, description="Optional request-per-minute limit")

    def to_router_model(self, route_name: str) -> dict[str, Any]:
        item: dict[str, Any] = {
            "model_name": route_name,
            "litellm_params": dict(self.litellm_params),
        }
        if self.model_info:
            item["model_info"] = dict(self.model_info)
        if self.tpm is not None:
            item["tpm"] = self.tpm
        if self.rpm is not None:
            item["rpm"] = self.rpm
        return item


class AIRouteItem(BaseModel):
    name: str = Field(..., description="The public route name used to call a LiteLLM model group")
    type: AIModelType = Field(..., description="The route capability type")
    deployments: list[AIRouteDeploymentItem] = Field(
        ..., min_length=1, description="Deployments participating in this route"
    )
    help: str | None = Field(default=None, description="Description of the route")
    kind: Literal["route"] = "route"

    def to_catalog_item(self) -> AICatalogItem:
        return AICatalogItem(name=self.name, kind="route", type=self.type, help=self.help)

    def to_router_models(self) -> list[dict[str, Any]]:
        return [deployment.to_router_model(self.name) for deployment in self.deployments]

    @property
    def dimension(self) -> int | None:
        values = {
            int(deployment.model_info["dimension"])
            for deployment in self.deployments
            if deployment.model_info.get("dimension") is not None
        }
        if len(values) > 1:
            raise ValueError(f"Route '{self.name}' has inconsistent embedding dimensions: {sorted(values)}")
        return next(iter(values), None)


class AIAliasItem(BaseModel):
    name: str = Field(..., description="The public alias name")
    type: AIModelType = Field(..., description="The alias capability type")
    target: str = Field(..., description="The target model, route, or alias name")
    help: str | None = Field(default=None, description="Description of the alias")
    kind: Literal["alias"] = "alias"

    def to_catalog_item(self) -> AICatalogItem:
        return AICatalogItem(name=self.name, kind="alias", type=self.type, help=self.help, target=self.target)


class AICollectionItem(BaseModel):
    name: str = Field(..., description="The collection name")
    type: AIModelType = Field(..., description="The collection capability type")
    members: list[str] = Field(..., min_length=1, description="Model, route, or alias names in this collection")
    default: str | None = Field(default=None, description="Default member name")
    help: str | None = Field(default=None, description="Description of the collection")
    kind: Literal["collection"] = "collection"

    def to_catalog_item(self) -> AICatalogItem:
        return AICatalogItem(name=self.name, kind="collection", type=self.type, help=self.help)


class AIRouterSettings(BaseModel):
    routing_strategy: str = Field(default="simple-shuffle", description="LiteLLM Router routing strategy")
    num_retries: int | None = Field(default=None, description="LiteLLM retry count")
    request_timeout: float | None = Field(default=None, description="LiteLLM request timeout")
    allowed_fails: int | None = Field(default=None, description="Failures before cooldown")
    cooldown_time: float | None = Field(default=None, description="Cooldown duration in seconds")
    enable_pre_call_checks: bool | None = Field(default=None, description="Enable LiteLLM pre-call checks")
    fallbacks: list[dict[str, list[str]]] = Field(default_factory=list, description="LiteLLM fallback config")
    context_window_fallbacks: list[dict[str, list[str]]] = Field(
        default_factory=list, description="LiteLLM context-window fallback config"
    )
    content_policy_fallbacks: list[dict[str, list[str]]] = Field(
        default_factory=list, description="LiteLLM content-policy fallback config"
    )

    def to_router_kwargs(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        return {key: value for key, value in data.items() if value not in ({}, [])}
