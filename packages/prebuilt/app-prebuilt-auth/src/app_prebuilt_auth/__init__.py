"""Complete authentication prebuilt with all models and optional provider activation."""

from . import models as models
from .setup import create_auth_router, install_auth

__all__ = ["create_auth_router", "install_auth", "models"]
