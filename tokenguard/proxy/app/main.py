from fastapi import FastAPI
from app.proxy import router as proxy_router
from app.health import router as health_router

app = FastAPI(title="TokenGuard Proxy", version="0.1.0")
app.include_router(proxy_router)
app.include_router(health_router, prefix="/health")


@app.get("/")
def root():
    return {"status": "ok", "service": "tokenguard-proxy"}
