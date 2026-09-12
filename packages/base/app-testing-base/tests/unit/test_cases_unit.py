"""Unit tests verifying UnitTest base class inheritance and helpers."""

from typing import Annotated

from app_testing_base import UnitTest
from fastapi import Depends


class ServiceA:
    def compute(self) -> int:
        return 42


class ServiceB:
    def __init__(self, service_a: Annotated[ServiceA, Depends()]):
        self.service_a = service_a

    def run(self) -> int:
        return self.service_a.compute() * 2


class TestUnitBaseClass(UnitTest):
    def test_mocker_and_resolve(self):
        # 1. Use self.mocker directly
        mock_a = self.mocker.MagicMock(spec=ServiceA)
        mock_a.compute.return_value = 100

        # 2. Use self.resolve with overrides
        service_b = self.resolve(ServiceB, overrides={ServiceA: mock_a})

        assert service_b.run() == 200
        mock_a.compute.assert_called_once()
