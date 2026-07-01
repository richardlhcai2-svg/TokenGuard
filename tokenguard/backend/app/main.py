import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.endpoints import proxy_router, router, set_proxy_secret


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: configure proxy secret
    set_proxy_secret(os.getenv("PROXY_SECRET", ""))
    yield
    # Shutdown: cleanup


app = FastAPI(
    title="TokenGuard Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
app.include_router(proxy_router, prefix="/internal")


@app.get("/health")
def health():
    return {"status": "ok", "service": "tokenguard-backend"}
