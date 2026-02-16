from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import run_migrations
from app.routers.chat import router as chat_router
from app.routers.conversations import router as conversations_router
from app.routers.docs import router as docs_router
from app.routers.providers import router as providers_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await run_migrations()
    yield


app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(docs_router)
app.include_router(providers_router)


@app.get("/healthz", tags=["system"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
