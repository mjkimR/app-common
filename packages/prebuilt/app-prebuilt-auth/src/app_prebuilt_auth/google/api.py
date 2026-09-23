from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from app_prebuilt_auth.user.exceptions import InvalidCredentialsException, UserAlreadyExistsException

from .config import GoogleAuthSettings, get_google_auth_settings
from .schemas import GoogleLoginOptions, GoogleLoginResult
from .usecases import GoogleAuthUseCase

router = APIRouter(prefix="/auth/google", tags=["Google authentication"])
BROWSER_COOKIE = "app_google_browser"
EXCHANGE_COOKIE = "app_google_exchange"


def enabled(settings: Annotated[GoogleAuthSettings, Depends(get_google_auth_settings)]) -> GoogleAuthSettings:
    if not settings.enabled:
        raise HTTPException(404, "Google login is not enabled")
    return settings


def cookie(response: Response, name: str, value: str, settings: GoogleAuthSettings, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="none" if name == BROWSER_COOKIE and settings.response_mode == "form_post" else "lax",
        path=settings.cookie_path,
    )


@router.get("/options", response_model=GoogleLoginOptions)
async def options(settings: Annotated[GoogleAuthSettings, Depends(get_google_auth_settings)]) -> GoogleLoginOptions:
    return GoogleLoginOptions(enabled=settings.enabled)


@router.get("/start")
async def start(
    settings: Annotated[GoogleAuthSettings, Depends(enabled)], use_case: Annotated[GoogleAuthUseCase, Depends()]
) -> RedirectResponse:
    url, browser = await use_case.begin()
    response = RedirectResponse(url, status_code=303)
    response.headers["Cache-Control"] = "no-store"
    cookie(response, BROWSER_COOKIE, browser, settings, 600)
    return response


@router.get("/callback")
async def callback(
    request: Request,
    settings: Annotated[GoogleAuthSettings, Depends(enabled)],
    use_case: Annotated[GoogleAuthUseCase, Depends()],
    state: Annotated[str, Query(max_length=256)] = "",
    code: Annotated[str, Query(max_length=4096)] = "",
    error: Annotated[str, Query(max_length=256)] = "",
) -> Response:
    if settings.response_mode != "query":
        return Response(
            status_code=405, headers={"Allow": "POST", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
        )
    return await complete_callback(request, settings, use_case, state, code, error)


@router.post("/callback")
async def callback_form_post(
    request: Request,
    settings: Annotated[GoogleAuthSettings, Depends(enabled)],
    use_case: Annotated[GoogleAuthUseCase, Depends()],
    state: Annotated[str, Form(max_length=256)] = "",
    code: Annotated[str, Form(max_length=4096)] = "",
    error: Annotated[str, Form(max_length=256)] = "",
) -> Response:
    if settings.response_mode != "form_post":
        return Response(
            status_code=405, headers={"Allow": "GET", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
        )
    return await complete_callback(request, settings, use_case, state, code, error)


async def complete_callback(
    request: Request,
    settings: GoogleAuthSettings,
    use_case: GoogleAuthUseCase,
    state: str,
    code: str,
    error: str,
) -> RedirectResponse:
    outcome, exchange = "failed", None
    try:
        if not error and state and code:
            exchange = await use_case.callback(state, request.cookies.get(BROWSER_COOKIE, ""), code)
            outcome = "complete"
    except UserAlreadyExistsException:
        outcome = "existing_account"
    except Exception:
        # Never expose provider responses or authorization codes in logs or redirects.
        outcome = "failed"
    response = RedirectResponse(settings.frontend_url + "?google=" + outcome, status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    cookie(response, BROWSER_COOKIE, "", settings, 0)
    if exchange:
        cookie(response, EXCHANGE_COOKIE, exchange, settings, 60)
    return response


@router.post("/exchange", response_model=GoogleLoginResult)
async def exchange(
    request: Request,
    response: Response,
    settings: Annotated[GoogleAuthSettings, Depends(enabled)],
    use_case: Annotated[GoogleAuthUseCase, Depends()],
) -> GoogleLoginResult:
    origin = urlsplit(settings.frontend_url)
    if request.headers.get("origin") != f"{origin.scheme}://{origin.netloc}":
        raise InvalidCredentialsException()
    result = await use_case.finish(request.cookies.get(EXCHANGE_COOKIE, ""))
    cookie(response, EXCHANGE_COOKIE, "", settings, 0)
    response.headers["Cache-Control"] = "no-store"
    return result
