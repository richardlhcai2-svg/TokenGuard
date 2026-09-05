import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .dashboard import router as dashboard_router
from .health import router as health_router
from .proxy import router as proxy_router
from .collector import start_collector_loop
from .queue import start_storage_worker, flush_remaining


def _get_store():
    try:
        from tokenguard.storage import UsageStore
        return UsageStore()
    except Exception:
        try:
            from ..storage import UsageStore
            return UsageStore()
        except Exception:
            return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = _get_store()
    worker_task = asyncio.create_task(start_storage_worker(store))
    collector_task = asyncio.create_task(start_collector_loop(interval_seconds=5.0))
    try:
        yield
    finally:
        collector_task.cancel()
        worker_task.cancel()
        try:
            await asyncio.gather(collector_task, worker_task, return_exceptions=True)
        except Exception:
            pass
        if store is not None:
            await flush_remaining(store)


app = FastAPI(title="TokenGuard Proxy", version="0.1.0", lifespan=lifespan)
app.include_router(dashboard_router)
app.include_router(health_router, prefix="/health")
app.include_router(proxy_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "tokenguard-proxy", "dashboard": "/dashboard"}
