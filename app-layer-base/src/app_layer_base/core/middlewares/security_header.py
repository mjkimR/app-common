from typing import ClassVar

from fastapi import FastAPI
from loguru import logger
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app_layer_base.config import get_app_settings


class SecurityHeaderMiddleware:
    """Pure ASGI Middleware to add security headers to responses"""

    PRODUCTION_CSP: ClassVar[bytes] = b"default-src 'self'"
    DEVELOPMENT_CSP: ClassVar[bytes] = b"default-src 'self' 'unsafe-inline' 'unsafe-eval' ws:;"
    DOCS_CSP: ClassVar[bytes] = (
        b"default-src 'self'; "
        b"script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
        b"style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
        b"img-src 'self' data: fastapi.tiangolo.com; "
        b"font-src 'self' data: cdn.jsdelivr.net; "
        b"connect-src 'self'"
    )
    DOCS_PATHS: ClassVar[frozenset[str]] = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})
    HSTS_HEADER: ClassVar[tuple[bytes, bytes]] = (
        b"strict-transport-security",
        b"max-age=31536000; includeSubDomains",
    )

    # Base headers safe to apply in all environments
    BASE_HEADERS: ClassVar[list[tuple[bytes, bytes]]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    ]

    def __init__(self, app: ASGIApp, is_production: bool | None = None):
        self.app = app
        app_env = "override"
        if is_production is None:
            settings = get_app_settings()
            is_production = settings.is_production
            app_env = settings.APP_ENV

        if is_production:
            self.security_headers = self._build_headers(csp=self.PRODUCTION_CSP, include_hsts=True)
            self.docs_security_headers = self._build_headers(csp=self.DOCS_CSP, include_hsts=True)
        else:
            logger.info(
                "SecurityHeaderMiddleware running in development mode (APP_ENV={}). "
                "HSTS is disabled and CSP is relaxed.",
                app_env,
            )
            self.security_headers = self._build_headers(csp=self.DEVELOPMENT_CSP, include_hsts=False)
            self.docs_security_headers = self._build_headers(csp=self.DOCS_CSP, include_hsts=False)

    def _build_headers(self, csp: bytes, include_hsts: bool) -> list[tuple[bytes, bytes]]:
        headers = list(self.BASE_HEADERS)
        if include_hsts:
            headers.append(self.HSTS_HEADER)
        headers.append((b"content-security-policy", csp))
        return headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        security_headers = self.docs_security_headers if scope.get("path") in self.DOCS_PATHS else self.security_headers

        async def send_wrapper(message: Message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(security_headers)
                message = {**message, "headers": headers}

            await send(message)

        await self.app(scope, receive, send_wrapper)


def add_middleware(app: FastAPI, is_production: bool | None = None):
    app.add_middleware(SecurityHeaderMiddleware, is_production=is_production)
