from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.deps import get_redis_client, close_redis
from app.api import auth
from app.api import admin as admin_api

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_redis_client()
    yield
    await close_redis()
    
app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(admin_api.router, prefix="/api")

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head>
            <title>Authentication Anomaly Detection</title>
        </head>
        <body style="font-family:Arial;text-align:center;margin-top:100px;">
            <h1 style="color:#008000;">Authentication Anomaly Detection</h1>
            <p style="color:#32cd32;">Detect anomaly during authentication and prevent financial frauds.</p>
            <div>
                <a href="/docs"><button>API Docs</button></a>
            </div>
        </body>
    </html>
    """
    
@app.get("/health")
async def health_check():
    return {"message": "Server is running."}
