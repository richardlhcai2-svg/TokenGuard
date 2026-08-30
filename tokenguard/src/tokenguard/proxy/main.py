import asyncio
from fastapi import FastAPI
from .dashboard import router as dashboard_router
from .health import router as health_router
from .proxy import router as proxy_router
from .collector import start_collector_loop

app = FastAPI(title="TokenGuard Proxy", version="0.1.0")
app.include_router(dashboard_router)
app.include_router(health_router, prefix="/health")
app.include_router(proxy_router)


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(start_collector_loop(interval_seconds=3.0))


@app.get("/")
def root():
    return {"status": "ok", "service": "tokenguard-proxy", "dashboard": "/dashboard"}
