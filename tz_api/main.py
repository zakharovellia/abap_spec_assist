from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.db import dispose_engine
from tz_api.routes import (
    conversations_router,
    documents_router,
    feedback_router,
    generation_router,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await dispose_engine()


app = FastAPI(
    title="ABAP Spec Assist API",
    description="Помощник написания ТЗ для SAP-консультантов",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(documents_router)
app.include_router(conversations_router)
app.include_router(generation_router)
app.include_router(feedback_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
