from app_layer_base.base.repos.base import BaseRepository

from .models import User
from .schemas import UserDbCreate, UserDbUpdate


class UserRepository(BaseRepository[User, UserDbCreate, UserDbUpdate, UserDbUpdate]):
    """Repository for User model."""

    model = User

    async def get_by_email(self, session, email: str) -> User | None:
        """Get a user by email."""
        stmt = self._select(where=User.email == email)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
