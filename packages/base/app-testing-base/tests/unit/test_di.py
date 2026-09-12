"""Unit tests for FastAPI dependency injection resolver."""

from typing import Annotated

from app_testing_base.di import MockRequest, resolve_dependency
from fastapi import Depends, Request


class EngineService:
    def __init__(self, mode: str = "turbo"):
        self.mode = mode


class CarService:
    def __init__(self, engine: Annotated[EngineService, Depends()]):
        self.engine = engine


class RequestAwareService:
    def __init__(self, request: Request, car: Annotated[CarService, Depends()]):
        self.request = request
        self.car = car


class ComplexUseCase:
    def __init__(
        self,
        service: Annotated[RequestAwareService, Depends()],
        extra_info: str = "default_info",
    ):
        self.service = service
        self.extra_info = extra_info


def test_resolve_simple_dependency():
    car = resolve_dependency(CarService)
    assert isinstance(car, CarService)
    assert isinstance(car.engine, EngineService)
    assert car.engine.mode == "turbo"


def test_resolve_with_state_and_request():
    mock_db = object()
    use_case = resolve_dependency(ComplexUseCase, state={"db": mock_db})

    assert isinstance(use_case, ComplexUseCase)
    assert isinstance(use_case.service.request, MockRequest)
    assert use_case.service.request.state.db is mock_db
    assert use_case.extra_info == "default_info"


def test_resolve_with_overrides():
    custom_engine = EngineService(mode="eco")
    car = resolve_dependency(CarService, overrides={EngineService: custom_engine})

    assert car.engine is custom_engine
    assert car.engine.mode == "eco"
