from app_prebuilt_auth.user.models import User

from .base import UserUseCase


class AuthenticateUserUseCase(UserUseCase):
    async def execute(self, email: str, password: str) -> User | None:
        # Commit an upgraded password hash before issuing tokens tied to that hash.
        async with self.transaction() as session:
            user = await self.service.authenticate(session, email=email, password=password)
        return user
