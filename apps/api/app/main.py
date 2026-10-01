from fastapi import FastAPI, Header, HTTPException
from .settings import settings

app = FastAPI(title=settings.app_name, version="0.1.0")

@app.get("/health")
def health():
    return {
        "service": "nexa-api",
        "status": "ok",
        "environment": settings.environment,
        "ai_enabled": settings.ai_enabled,
    }

@app.get("/v1/context")
def context(x_org_id: str | None = Header(default=None)):
    if not x_org_id:
        raise HTTPException(status_code=400, detail="X-Org-Id header is required")
    return {"organisation_id": x_org_id}
