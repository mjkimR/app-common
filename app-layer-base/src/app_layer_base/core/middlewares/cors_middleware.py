from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app_layer_base.config import get_app_settings


def add_middleware(app: FastAPI):
    settings = get_app_settings()
    allow_origins = settings.CORS_ALLOWED_ORIGINS
    allow_origin_regex = settings.CORS_ALLOW_ORIGIN_REGEX
    allow_credentials = settings.CORS_ALLOW_CREDENTIALS

    # If origins are wildcard, allow_credentials must be False for security and to prevent FastAPI errors
    if "*" in allow_origins:
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
