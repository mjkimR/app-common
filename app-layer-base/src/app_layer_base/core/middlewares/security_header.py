from typing import ClassVar

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeaderMiddleware:
    """Pure ASGI Middleware to add security headers to responses"""

    # Base headers safe to apply in all environments
    BASE_HEADERS: ClassVar[list[tuple[bytes, bytes]]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    ]

    def __init__(self, app: ASGIApp, is_production: bool = True):
        self.app = app

        # Compute the headers list once during initialization to optimize performance
        self.security_headers = list(self.BASE_HEADERS)

        if is_production:
            self.security_headers.extend(
                [
                    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
                    (b"content-security-policy", b"default-src 'self'"),
                ]
            )
        else:
            # Development environment: Exclude HSTS entirely, relax CSP
            self.security_headers.extend(
                [
                    (b"content-security-policy", b"default-src 'self' 'unsafe-inline' 'unsafe-eval' ws:;"),
                ]
            )

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self.security_headers)
                message = {**message, "headers": headers}

            await send(message)

        await self.app(scope, receive, send_wrapper)


def add_middleware(app: FastAPI, is_production: bool = False):
    # Pass the is_production flag based on your environment settings
    app.add_middleware(SecurityHeaderMiddleware, is_production=is_production)
