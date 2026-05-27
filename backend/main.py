"""
main.py — application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import init_db, close_db
from app.deps import get_redis_client, close_redis
from app.db import models as _models  # noqa: F401 — registers models with Base.metadata
from app.api import auth

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()        # create tables if missing (dev); use Alembic in prod
    get_redis_client()     # warm up Redis connection on first worker start
    yield
    # Shutdown
    await close_redis()    # drain Redis connection
    await close_db()       # drain PostgreSQL pool


app = FastAPI(
    title="Authentication Anomaly Detection",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head><title>Authentication Anomaly Detection</title></head>
        <body style="font-family:Arial;text-align:center;margin-top:100px;">
            <h1 style="color:#008000;">Authentication Anomaly Detection</h1>
            <p style="color:#32cd32;">Detect anomalies during authentication and prevent financial fraud.</p>
            <div><a href="/docs"><button>API Docs</button></a></div>
        </body>
    </html>
    """


@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Server is running."}