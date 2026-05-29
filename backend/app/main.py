from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, profile, public, sources
from app.core.config import get_settings
from app.db import init_db


settings = get_settings()
app = FastAPI(title="cipher API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    if settings.init_db_on_startup:
        init_db()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "cipher-api"}


app.include_router(profile.router)
app.include_router(sources.router)
app.include_router(analysis.router)
app.include_router(public.router)

