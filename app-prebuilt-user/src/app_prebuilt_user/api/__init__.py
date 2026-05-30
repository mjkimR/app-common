from .v1.admin import router as v1_admin_router
from .v1.login import router as v1_login_router
from .v1.users import router as v1_users_router

v1_users_router.include_router(v1_admin_router)
v1_users_router.include_router(v1_login_router)

__all__ = [
    "v1_users_router",
]
