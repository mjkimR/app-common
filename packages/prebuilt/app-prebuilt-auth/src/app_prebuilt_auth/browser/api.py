from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app_prebuilt_auth.user.api.v1.login import login as password_login
from app_prebuilt_auth.user.token_schemas import Token

from .config import BrowserAuthSettings, get_browser_auth_settings
from .usecases import BrowserSessionUseCase


def require_browser_request(
    request: Request, settings: Annotated[BrowserAuthSettings, Depends(get_browser_auth_settings)]
) -> None:
    # Custom header forces CORS preflight; exact origin validation also excludes
    # hostile same-site subdomains. Never allow credentialed wildcard origins.
    origin = request.headers.get("origin")
    expected = str(request.base_url).rstrip("/")
    if request.headers.get("x-browser-session") != "1" or origin not in [expected, *settings.allowed_origins]:
        raise HTTPException(403, "Invalid browser session origin")


def set_cookie(request: Request, response: Response, settings: BrowserAuthSettings, key: str, max_age: int) -> None:
    secure = settings.cookie_secure
    if secure is None:
        secure = request.url.scheme == "https" or request.url.hostname not in {"localhost", "127.0.0.1", "::1"}
    response.set_cookie(
        settings.cookie_name,
        key,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=settings.cookie_path,
    )
    response.headers["Cache-Control"] = "no-store"


async def establish(
    request: Request,
    response: Response,
    tokens: Token,
    settings: BrowserAuthSettings,
    use_case: BrowserSessionUseCase,
) -> Token:
    key = await use_case.begin(tokens, request.cookies.get(settings.cookie_name, ""))
    set_cookie(request, response, settings, key, int(use_case.service.lifetime.total_seconds()))
    return tokens.model_copy(update={"refresh_token": None})


router = APIRouter(prefix="/auth/browser", tags=["Browser sessions"], dependencies=[Depends(require_browser_request)])


@router.post("/login", response_model=Token, response_model_exclude_none=True)
async def login(
    request: Request,
    response: Response,
    tokens: Annotated[Token, Depends(password_login)],
    settings: Annotated[BrowserAuthSettings, Depends(get_browser_auth_settings)],
    use_case: Annotated[BrowserSessionUseCase, Depends()],
) -> Token:
    return await establish(request, response, tokens, settings, use_case)


@router.post("/refresh", response_model=Token, response_model_exclude_none=True)
async def refresh(
    request: Request,
    response: Response,
    settings: Annotated[BrowserAuthSettings, Depends(get_browser_auth_settings)],
    use_case: Annotated[BrowserSessionUseCase, Depends()],
) -> Token:
    key = request.cookies.get(settings.cookie_name, "")
    tokens = await use_case.refresh(key)
    set_cookie(request, response, settings, key, int(use_case.service.lifetime.total_seconds()))
    return tokens


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    settings: Annotated[BrowserAuthSettings, Depends(get_browser_auth_settings)],
    use_case: Annotated[BrowserSessionUseCase, Depends()],
) -> None:
    await use_case.logout(request.cookies.get(settings.cookie_name, ""))
    set_cookie(request, response, settings, "", 0)
