import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.endpoints import proxy_router, router, set_proxy_secret
from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.api.orgs import router as orgs_router
from app.api.usage import router as usage_router
from app.api.recommendations import router as recommendations_router
from app.api.reports import router as reports_router
from app.api.subscriptions import router as subscriptions_router


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
app.include_router(alerts_router)
app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(usage_router)
app.include_router(recommendations_router)
app.include_router(reports_router)
app.include_router(subscriptions_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "tokenguard-backend"}
