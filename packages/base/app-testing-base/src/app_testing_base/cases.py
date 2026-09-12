"""Base test classes for Integration, E2E, and Unit test suites."""

from collections.abc import Callable
from typing import Any, ClassVar

import pytest
from httpx import AsyncClient
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from app_testing_base.db.helpers import refresh_get
from app_testing_base.di.resolver import resolve_dependency


class IntegrationTest:
    """Base class for integration tests interacting with database and usecases.

    Automatically injects `self.session`, marks the class with `@pytest.mark.integrate`,
    and provides `self.resolve(...)` and `self.refresh(...)` helpers.
    """

    __test__ = False
    pytestmark: ClassVar[list[pytest.MarkDecorator]] = [pytest.mark.integrate]

    session: AsyncSession

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.__test__ = True

    @pytest.fixture(autouse=True)
    def _inject_integration_fixtures(self, session: AsyncSession) -> None:
        self.session = session

    def resolve[T](
        self,
        target: Callable[..., T] | type[T],
        overrides: dict[Any, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> T:
        """Resolve dependency tree with current session pre-bound to get_session, AsyncSession, and request.state.db."""
        from app_layer_base.core.database.deps import get_session

        base_overrides: dict[Any, Any] = {
            get_session: self.session,
            AsyncSession: self.session,
        }
        if overrides:
            base_overrides.update(overrides)

        merged_state = {"db": self.session}
        if state:
            merged_state.update(state)
        return resolve_dependency(target, state=merged_state, overrides=base_overrides)

    async def refresh[T](self, model: type[T], ident: Any) -> T | None:
        """Clear identity map cache and reload fresh DB record."""
        return await refresh_get(self.session, model, ident)


class E2ETest:
    """Base class for E2E tests verifying HTTP API routers.

    Automatically injects `self.client` and `self.session`, marks the class with
    `@pytest.mark.e2e` and `@pytest.mark.real_commit`, and provides `self.url(...)`
    and `self.refresh(...)` helpers.
    """

    __test__ = False
    pytestmark: ClassVar[list[pytest.MarkDecorator]] = [pytest.mark.e2e, pytest.mark.real_commit]

    client: AsyncClient
    session: AsyncSession
    base_url: str = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.__test__ = True

    @pytest.fixture(autouse=True)
    def _inject_e2e_fixtures(self, client: AsyncClient, session: AsyncSession) -> None:
        self.client = client
        self.session = session

    def url(self, path: str = "") -> str:
        """Build endpoint URL from base_url."""
        base = self.base_url.rstrip("/")
        sub = path.strip("/")
        if not sub:
            return base
        return f"{base}/{sub}"

    async def refresh[T](self, model: type[T], ident: Any) -> T | None:
        """Clear identity map cache and reload fresh DB record after API calls."""
        return await refresh_get(self.session, model, ident)


class UnitTest:
    """Base class for isolated unit tests with mock utilities.

    Automatically injects `self.mocker` from pytest-mock and provides `self.resolve(...)`.
    """

    __test__ = False
    mocker: MockerFixture

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.__test__ = True

    @pytest.fixture(autouse=True)
    def _inject_unit_fixtures(self, mocker: MockerFixture) -> None:
        self.mocker = mocker

    def resolve[T](
        self,
        target: Callable[..., T] | type[T],
        overrides: dict[Any, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> T:
        """Resolve dependency tree with mock state and overrides."""
        return resolve_dependency(target, state=state, overrides=overrides)
