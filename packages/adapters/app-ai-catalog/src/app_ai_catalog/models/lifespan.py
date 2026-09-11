from contextlib import asynccontextmanager

from fastapi import FastAPI

from app_ai_catalog.models.client import AIClient
from app_ai_catalog.models.instance import close_ai_client, setup_ai_client


@asynccontextmanager
async def lifespan_ai_client(app: FastAPI, config_path: str = AIClient.DEFAULT_PATH):
    """Lifespan context manager to initialize and cleanup the AI client."""
    setup_ai_client(config_path=config_path)

    yield

    close_ai_client()
