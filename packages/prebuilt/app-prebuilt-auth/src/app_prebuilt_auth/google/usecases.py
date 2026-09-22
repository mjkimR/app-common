from typing import Annotated, Literal, cast

from app_layer_base.utils.time_util import get_current_utc_time
from fastapi import Depends
from sqlalchemy.exc import IntegrityError

from app_prebuilt_auth.user.database import UserTransaction, get_user_transaction
from app_prebuilt_auth.user.exceptions import InvalidCredentialsException
from app_prebuilt_auth.user.token_schemas import Token

from .schemas import GoogleLoginResult
from .services import GoogleAuthService, digest


class GoogleAuthUseCase:
    def __init__(
        self,
        service: Annotated[GoogleAuthService, Depends()],
        transaction: Annotated[UserTransaction, Depends(get_user_transaction)],
    ):
        self.service = service
        self.transaction = transaction

    async def begin(self) -> tuple[str, str]:
        async with self.transaction() as session:
            return await self.service.begin(session)

    async def callback(self, state: str, browser: str, code: str) -> str:
        # Consume state in its own transaction, even when the provider rejects the code.
        async with self.transaction() as session:
            flow = await self.service.repo.consume(session, digest(state), digest(browser), get_current_utc_time())
        if flow is None or flow.nonce is None or flow.verifier is None:
            raise InvalidCredentialsException()
        identity = await self.service.provider.exchange(code, flow.verifier, flow.nonce)
        try:
            async with self.transaction() as session:
                user = await self.service.register(session, identity)
                return await self.service.handoff(session, user)
        except IntegrityError:
            # Concurrent first logins may register the same subject. Never infer a link from email.
            async with self.transaction() as session:
                user = await self.service.repo.identity_user(session, identity.subject)
                if user is None:
                    raise InvalidCredentialsException() from None
                return await self.service.handoff(session, user)

    async def finish(self, exchange: str) -> GoogleLoginResult:
        async with self.transaction() as session:
            flow = await self.service.repo.consume(session, digest(exchange), digest(exchange), get_current_utc_time())
            user = await self.service.repo.user(session, flow.user_id) if flow is not None and flow.user_id else None
            if user is None:
                raise InvalidCredentialsException()
            status = user.approval_status if user.is_active else "suspended"
            tokens = None
            if status == "approved":
                users = self.service.users
                tokens = Token(
                    access_token=users.create_access_token(user),
                    refresh_token=users.create_refresh_token(user),
                    token_type="bearer",
                    expires_in=users.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                )
            return GoogleLoginResult(
                status=cast(Literal["approved", "pending", "rejected", "suspended"], status),
                email=user.email,
                tokens=tokens,
            )
