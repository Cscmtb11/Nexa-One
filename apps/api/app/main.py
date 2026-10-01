from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import Base, engine
from .settings import settings
from .routers import auth, organisations, facilities

app = FastAPI(title=settings.app_name, version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    if settings.environment != "production":
        Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"service":"nexa-api","status":"ok","environment":settings.environment,"ai_enabled":settings.ai_enabled,"version":"0.3.0"}

app.include_router(auth.router)
app.include_router(organisations.router)
app.include_router(facilities.router)
