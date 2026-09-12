"""Resolve FastAPI `Annotated[T, Depends()]` trees without an app or request."""

import inspect
from collections.abc import Callable
from types import SimpleNamespace
from typing import Annotated, Any, cast, get_args, get_origin

from fastapi import Request
from fastapi.params import Depends


class MockRequest:
    """Mock class that mimics the state of a FastAPI Request object."""

    def __init__(self, state_attrs: dict[str, Any] | None = None):
        self.state = SimpleNamespace(**(state_attrs or {}))
        self.scope = {"type": "http"}


class DependencyResolutionError(Exception):
    """Raised when resolve_dependency cannot resolve a required dependency."""


def resolve_dependency[T](
    target: Callable[..., T] | type[T],
    state: dict[str, Any] | None = None,
    overrides: dict[Any, Any] | None = None,
) -> T:
    """Test helper that resolves FastAPI dependency trees and instantiates objects.

    Args:
        target: Class or function to instantiate/call (UseCase, Service, Repository, etc.)
        state: Key-value pairs to inject into request.state (e.g., {"db": session})
        overrides: Replace specific dependency functions or types with mocks or instances {get_db: mock_session}
    """
    if overrides is None:
        overrides = {}

    # 1. Check overrides (highest priority)
    if target in overrides:
        return cast(T, overrides[target])

    # 2. Inject MockRequest when Request object is needed
    if target is Request:
        return cast(T, MockRequest(state))

    # 3. Check if callable (Function or Class)
    if inspect.isclass(target):
        func = target.__init__
    elif callable(target):
        func = target
    else:
        return cast(T, target)

    sig = inspect.signature(func)
    kwargs: dict[str, Any] = {}

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        # Detect Request object type hint
        if param.annotation is Request:
            kwargs[param_name] = MockRequest(state)
            continue

        dependency_target = None

        # Case A: Annotated[Type, Depends(...)]
        if get_origin(param.annotation) is Annotated:
            for arg in get_args(param.annotation)[1:]:
                if isinstance(arg, Depends):
                    dependency_target = arg.dependency or get_args(param.annotation)[0]
                    break

        # Case B: Depends(...) (Default value)
        if dependency_target is None and isinstance(param.default, Depends):
            dependency_target = param.default.dependency or param.annotation

        # Recursive resolution
        if dependency_target:
            kwargs[param_name] = resolve_dependency(dependency_target, state, overrides)
        elif param.default is not inspect.Parameter.empty:
            kwargs[param_name] = param.default
        else:
            target_name = getattr(target, "__name__", str(target))
            ann_name = getattr(param.annotation, "__name__", str(param.annotation))
            raise DependencyResolutionError(
                f"Cannot resolve required parameter '{param_name}: {ann_name}' of '{target_name}'. "
                f"It has no default value and is not annotated with Depends(). "
                f"Did you forget `Annotated[{ann_name}, Depends()]` or passing an override?"
            )

    # 4. Instantiate and return object
    if inspect.isclass(target):
        return cast(T, cast(Any, target)(**kwargs))
    return cast(T, cast(Any, func)(**kwargs))
